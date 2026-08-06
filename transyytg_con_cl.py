#!/usr/bin/env python3
"""
DCS Mission Translator - CLI Entry Point

Translates DCS World mission (.miz) files from English to Chinese using
the DeepSeek LLM API. Extracts dictionary files from .miz archives,
translates text content, and repackages them back.

Usage:
    python transyytg_con_cl.py --api-key YOUR_KEY --path /path/to/missions
    python transyytg_con_cl.py  # Interactive mode
"""

import os
import argparse
import json
import re
import sys
import logging
import hashlib

from util.system_prompt import system_prompt
from util.LLM_trans import LLM_trans_v2
from util.extract_miz import extract_specific_file, get_files
from util.intract_miz import dictionary_intract
from util.lua_reg import isMatchLua
from util.remote_cache import looking_translated, save_translated
from util.glossary import correct_translations, build_dynamic_glossary_prompt
from util.rollback import rollback_miz
from util.config import load_config, save_config, mask_api_key

CACHE_DIR = "./cache"

# ---------------------------------------------------------------------------
# Cache file naming
# ---------------------------------------------------------------------------
# New format:  md5_{hash}_translated.json  (with algorithm prefix)
# Old format:  {hash}_translated.json      (legacy, no prefix)
#
# The lookup tries new format first, falls back to old, and auto-migrates
# old files to new naming when found. This allows gradual migration while
# retaining access to all previously cached translations.
# ---------------------------------------------------------------------------

CACHE_PREFIX = "md5_"


def ensure_cache_dir():
    """Create the cache directory if it doesn't exist."""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)


def get_json_list(miz_path):
    """Get all intermediate JSON files in the directory (excluding _translateRef)."""
    json_list = []
    for root, dirs, files in os.walk(miz_path):
        for file in files:
            if file.endswith(".json") and not file.endswith("_translateRef.json"):
                json_list.append(os.path.join(root, file))
    return json_list


def filter_translatable(json_data):
    """
    Filter JSON data to only include translatable values.
    Skips: Name fields, DictKey entries, Lua code, very short strings.
    """
    filtered = {}
    for key, value in json_data.items():
        if "Name" in key:
            continue
        if "DictKey" in value:
            continue
        if isMatchLua(value):
            logging.info("Skipping Lua code: %s", value[:80])
            print(f"Skipping Lua code: {value[:80]}...")
            continue
        if len(value) < 2:
            continue
        filtered[key] = value
    return dict(sorted(filtered.items(), key=lambda item: item[0]))


def compute_content_hash(data):
    """
    Compute MD5 content hash for cache identification.

    Uses MD5 for its speed and compact 32-char hex output. While MD5 is
    cryptographically broken for adversarial collision resistance, for
    non-adversarial content-addressing of translation data the collision
    probability is astronomically low (~1 in 2^64 birthday bound).

    Returns:
        Prefixed hash string, e.g. "md5_a1b2c3d4e5f6..."
    """
    data_str = json.dumps(data, ensure_ascii=False, indent=4)
    md5_hex = hashlib.md5(data_str.encode("utf-8")).hexdigest()
    return CACHE_PREFIX + md5_hex


def find_cache_file(content_hash):
    """
    Find a cache file with backward compatibility.

    Tries new naming (md5_{hash}_translated.json) first, then falls back
    to old naming ({hash}_translated.json). If found via old name,
    renames the file to new naming for gradual migration.

    Args:
        content_hash: Prefixed hash, e.g. "md5_a1b2c3..."

    Returns:
        Path to the cache file, or None if not found.
    """
    # 1) Try new format: md5_{hash}_translated.json
    new_path = os.path.join(CACHE_DIR, f"{content_hash}_translated.json")
    if os.path.exists(new_path):
        return new_path

    # 2) Try old format (strip prefix): {hash}_translated.json
    if content_hash.startswith(CACHE_PREFIX):
        legacy_hash = content_hash[len(CACHE_PREFIX):]
        legacy_path = os.path.join(CACHE_DIR, f"{legacy_hash}_translated.json")
        if os.path.exists(legacy_path):
            # Auto-migrate: rename old → new
            print(f"Migrating cache: {legacy_hash} → {content_hash}")
            os.rename(legacy_path, new_path)
            return new_path

    return None


def lookup_translation(json_data_filtered, content_hash, use_remote=True):
    """
    Try to find existing translations: local cache → remote → None.
    Returns (translated_dict, existed) tuple.

    Local is checked first (instant disk read). Remote serves as a
    community supplement to fill gaps in the local cache.

    Backward-compatible: local cache lookup tries both new and legacy
    naming, and auto-migrates old files to new naming.
    """
    # 1) Try local cache first — instant, no network
    cache_path = find_cache_file(content_hash)
    if cache_path:
        with open(cache_path, "r", encoding="utf-8") as f:
            translated = json.load(f)
        print(f"Found in local cache: {content_hash}")
        # Optionally backfill remote so others benefit
        if use_remote:
            print(f"Backfilling remote: {content_hash}")
            success, msg = save_translated(content_hash, translated)
            if success:
                print(f"Saved to remote: {content_hash}")
            else:
                print(f"Remote backfill skipped: {msg}")
        return translated, True

    # 2) Try remote cache (if enabled)
    if use_remote:
        print(f"Not in local cache, trying remote: {content_hash}")
        is_remote, remote_content = looking_translated(content_hash)
        if is_remote:
            # Save to local cache for future instant access
            local_path = os.path.join(CACHE_DIR, f"{content_hash}_translated.json")
            with open(local_path, "w", encoding="utf-8") as f:
                json.dump(remote_content, f, ensure_ascii=False, indent=4)
            print(f"Found via remote, saved to local: {content_hash}")
            return remote_content, True
        print(f"No remote result: {content_hash}")

    # 3) Neither cache has it — need LLM translation
    print(f"No cached result, translation needed: {content_hash}")
    return None, False


def translate_via_llm(json_data_filtered, api_key, content_hash, use_remote=True):
    """
    Send translatable content to LLM for translation.
    Dynamically injects relevant glossary terms into the system prompt.
    Returns the translated dictionary.
    """
    # Build user message with <input_id> tagged text
    test_input = (
        "将以下英文翻译成中文，输出格式为<input_id>key</input_id><text>value</text>，"
        "其中key为DictKey_开头的键，value为翻译后的中文\n"
    )
    for key, value in json_data_filtered.items():
        test_input += f"<input_id>{key}</input_id><text>{value}</text>\n"

    # Build dynamic glossary appendix for terms found in this text
    dynamic_prompt = build_dynamic_glossary_prompt(json_data_filtered)
    full_system_prompt = system_prompt + dynamic_prompt

    try:
        translated_output = LLM_trans_v2(
            full_system_prompt, test_input, api_key,
            CACHE_DIR=CACHE_DIR, CONTENT_HASH=content_hash
        )
    except Exception as e:
        logging.error("Translation error: %s", e)
        print(f"Translation error: {e}")
        sys.exit(1)

    # Parse LLM output
    matches = re.findall(
        r'<input_id>(.*?)</input_id><text>(.*?)</text>',
        translated_output, re.DOTALL
    )

    if not matches:
        # Model returned unexpected format — save raw output for debugging
        debug_path = os.path.join(CACHE_DIR, f"{content_hash}_parse_error.txt")
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(translated_output)
        logging.error(
            "Parse failed: no <input_id> tags in LLM output. "
            "Raw output saved to %s", debug_path
        )
        print(f"ERROR: LLM returned unrecognizable format. Raw output: {debug_path}")
        sys.exit(1)

    translated_dict = {}
    for key, value in matches:
        translated_dict[key] = value.strip()

    expected = len(json_data_filtered)
    if len(translated_dict) < expected:
        logging.warning(
            "Parse incomplete: got %d/%d translations", len(translated_dict), expected
        )
        print(f"Warning: only {len(translated_dict)}/{expected} entries translated")

    # Save to remote (if enabled) and local
    if use_remote:
        print(f"Saving to remote: {content_hash}")
        success, msg = save_translated(content_hash, translated_dict)
        if success:
            print(f"Saved to remote successfully: {content_hash}")
        else:
            print(f"Failed to save to remote: {msg}")

    cache_path = os.path.join(CACHE_DIR, f"{content_hash}_translated.json")
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(translated_dict, f, ensure_ascii=False, indent=4)
    print(f"Saved to local cache: {content_hash}")

    return translated_dict


def write_translation_ref(json_path, json_data_filtered, translated_dict):
    """Write the translation reference file (English → Chinese mapping)."""
    translate_ref = {}
    for key, value in json_data_filtered.items():
        if key in translated_dict and translated_dict[key]:
            translate_ref[value] = translated_dict[key]
        else:
            print(f"Missing translation for key: {key}")

    ref_path = os.path.join(
        os.path.dirname(json_path),
        os.path.splitext(os.path.basename(json_path))[0] + "_translateRef.json"
    )
    with open(ref_path, "w", encoding="utf-8") as f:
        json.dump(translate_ref, f, ensure_ascii=False, indent=4)


def apply_translations(json_data, translated_dict, only_chs):
    """
    Merge translations back into the original JSON structure.
    Handles Script, Radio, and regular text formatting.
    """
    for key, value in json_data.items():
        if key not in translated_dict or not translated_dict[key]:
            continue

        translated_text = translated_dict[key]

        if only_chs:
            if "[Script]" in key:
                json_data[key] = "[Script]" + translated_text
            else:
                json_data[key] = translated_text
        elif "Radio" in key:
            json_data[key] = "[" + value + "][" + translated_text + "]"
        elif "Script" in key:
            json_data[key] = value + "[" + translated_text + "]"
        else:
            json_data[key] = value + "\n" + translated_text

    return json_data


def read_and_translate_json(json_path, api_key, only_chs, use_remote=True):
    """Process a single JSON file: filter, translate, merge, write back."""
    with open(json_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    # Filter to translatable entries
    json_data_filtered = filter_translatable(json_data)
    content_hash = compute_content_hash(json_data_filtered)

    # Lookup existing translation or translate
    translated_dict, existed = lookup_translation(
        json_data_filtered, content_hash, use_remote=use_remote
    )
    if not existed:
        translated_dict = translate_via_llm(
            json_data_filtered, api_key, content_hash, use_remote=use_remote
        )

    # Apply glossary-based corrections (revert over-translated terms, fix missed brevity)
    translated_dict = correct_translations(json_data_filtered, translated_dict)

    # Write translation reference
    write_translation_ref(json_path, json_data_filtered, translated_dict)

    # Apply translations back to original JSON
    json_data = apply_translations(json_data, translated_dict, only_chs)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)


def transyytg_con(api_key, remove_json, miz_path, only_chs, use_remote=True):
    """
    Main translation workflow:
    1. Find .miz files
    2. Extract dictionary from each
    3. Translate JSON content
    4. Repack into .miz archives
    """
    target_file_in_zip = "l10n/DEFAULT/dictionary"

    # Find and extract .miz files
    file_list = get_files(miz_path)
    print(f"Found {len(file_list)} .miz file(s):")
    for f in file_list:
        print(f"  {f}")

    if len(file_list) == 0:
        raise FileNotFoundError(
            f"No .miz files found in: {miz_path}\n"
            "Please verify the path is correct."
        )

    for file in file_list:
        extract_specific_file(
            file, target_file_in_zip,
            os.path.basename(file) + ".json",
            output_dir=os.path.dirname(file)
        )

    # Set up logging (avoid duplicate handlers on repeated calls)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        file_handler = logging.FileHandler(
            os.path.join(CACHE_DIR, "log.txt"), mode='a', encoding="utf-8"
        )
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logging.info("Starting translation task")
    print("Starting translation task...")

    # Process each JSON file
    json_list = get_json_list(miz_path)
    json_list.sort()
    print(f"Processing {len(json_list)} JSON file(s):")
    for f in json_list:
        print(f"  {f}")

    for file in json_list:
        try:
            print(f"\nProcessing: {file}")
            read_and_translate_json(file, api_key, only_chs, use_remote=use_remote)
            dictionary_intract(file)
            print(f"Merging into .miz: {file}")
            if remove_json:
                os.remove(file)
                print(f"Removed intermediate JSON: {file}")
        except Exception as e:
            logging.error("Error processing %s: %s", file, e)
            print(f"Error processing {file}: {e}")
            raise

    print("\nTranslation complete!")


# ---------------------------------------------------------------------------
# CLI Interface
# ---------------------------------------------------------------------------

DESCRIPTION = """
DCS Mission Translator v2.0 — 将DCS World .miz任务文件从英文翻译为中文
Translate DCS World .miz mission files from English to Chinese.

功能特点 Features:
  - 远程翻译缓存：共享翻译结果，"我为人人、人人为我"
  - 本地缓存：避免重复翻译相同内容
  - Lua感知过滤：自动跳过代码，仅翻译自然语言文本

要求:
  - DeepSeek API Key (https://platform.deepseek.com/)
  - DCS World .miz 任务文件
"""


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="DCS Mission Translator - DCS任务翻译工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例 Examples:
  python transyytg_con_cl.py --api-key sk-xxxx --path "E:/DCS/Missions"
  python transyytg_con_cl.py --api-key sk-xxxx --path ./missions --only-chs
  python transyytg_con_cl.py  # 交互模式 Interactive mode
        """,
    )
    parser.add_argument(
        "--api-key", type=str,
        help="DeepSeek API Key"
    )
    parser.add_argument(
        "--path", type=str,
        help="包含.miz任务文件的文件夹路径"
    )
    parser.add_argument(
        "--only-chs", action="store_true",
        help="仅输出中文（默认中英混排）"
    )
    parser.add_argument(
        "--remove-json", action="store_true",
        help="翻译完成后删除中间JSON文件"
    )
    parser.add_argument(
        "--no-remote", action="store_true",
        help="禁用远程缓存服务器（仅使用本地缓存和LLM翻译）"
    )
    parser.add_argument(
        "--rollback", action="store_true",
        help="回滚翻译：移除.miz中的中文翻译，恢复原始英文任务"
    )
    return parser.parse_args()


def interactive_mode():
    """Run the translator in interactive prompt mode with saved defaults."""
    cfg = load_config()

    print(DESCRIPTION)
    print("=" * 60)
    print("当前模型: deepseek-v4-pro (固定)")
    if cfg["use_remote_cache"]:
        print("远程缓存: 已启用")
    else:
        print("远程缓存: 已禁用")
    print("=" * 60)

    try:
        # API Key (show masked default if saved)
        default_key = cfg.get("api_key", "")
        prompt = "请输入API Key"
        if default_key:
            prompt += f" [默认: {mask_api_key(default_key)}]"
        api_key = input(prompt + ": ").strip()
        if not api_key and default_key:
            api_key = default_key
        if not api_key:
            print("错误：API Key不能为空。")
            sys.exit(1)

        # Mission path (show default if saved)
        default_path = cfg.get("path", "")
        prompt = "请输入任务文件夹路径"
        if default_path:
            prompt += f" [默认: {default_path}]"
        miz_path = input(prompt + ": ").strip()
        if not miz_path and default_path:
            miz_path = default_path
        if not os.path.exists(miz_path):
            print(f"错误：路径不存在: {miz_path}")
            sys.exit(1)

        miz_files = [f for f in os.listdir(miz_path) if f.endswith('.miz')]
        if not miz_files:
            print(f"错误：路径内没有找到.miz文件: {miz_path}")
            sys.exit(1)
        print(f"找到 {len(miz_files)} 个.miz文件")

        # Output mode
        default_only = cfg.get("only_chs", False)
        default_label = "仅中文" if default_only else "混排"
        choice = input(f"是否中英文混排？(y/n, 默认={default_label}): ").strip().lower()
        if choice == 'y':
            only_chs = False
        elif choice == 'n':
            only_chs = True
        else:
            only_chs = default_only

        # Remove JSON
        default_remove = cfg.get("remove_json", False)
        default_label = "是" if default_remove else "否"
        choice = input(f"是否删除中间JSON文件？(y/n, 默认={default_label}): ").strip().lower()
        if choice == 'y':
            remove_json = True
        elif choice == 'n':
            remove_json = False
        else:
            remove_json = default_remove

        # Remote cache
        default_remote = cfg.get("use_remote_cache", True)
        default_label = "启用" if default_remote else "禁用"
        choice = input(f"是否使用远程缓存服务器？(y/n, 默认={default_label}): ").strip().lower()
        if choice == 'y':
            use_remote = True
        elif choice == 'n':
            use_remote = False
        else:
            use_remote = default_remote

    except (KeyboardInterrupt, EOFError):
        print("\n已取消。")
        sys.exit(0)

    # Save config for next session
    save_config({
        "api_key": api_key,
        "path": miz_path,
        "only_chs": only_chs,
        "remove_json": remove_json,
        "use_remote_cache": use_remote,
    })

    transyytg_con(api_key, remove_json, miz_path, only_chs, use_remote=use_remote)


def main():
    """Main entry point."""
    ensure_cache_dir()
    args = parse_args()

    # --- Rollback mode ---
    if args.rollback:
        if not args.path:
            print("错误：回滚需要指定 --path")
            sys.exit(1)
        if not os.path.exists(args.path):
            print(f"错误：路径不存在: {args.path}")
            sys.exit(1)
        print("=" * 40)
        print("  翻译回滚 — 恢复原始英文任务")
        print("=" * 40)
        rollback_miz(args.path)
        print("完成！")
        return

    # --- Translate mode ---
    if args.api_key and args.path:
        # Command-line mode
        if not os.path.exists(args.path):
            print(f"错误：路径不存在: {args.path}")
            sys.exit(1)

        miz_files = [f for f in os.listdir(args.path) if f.endswith('.miz')]
        if not miz_files:
            print(f"错误：路径内没有找到.miz文件: {args.path}")
            sys.exit(1)

        use_remote = not args.no_remote

        print(DESCRIPTION)
        print(f"API Key: {'*' * 8}{args.api_key[-4:]}")
        print(f"路径: {args.path}")
        print(f"仅中文: {args.only_chs}")
        print(f"删除JSON: {args.remove_json}")
        print(f"远程缓存: {'禁用' if args.no_remote else '启用'}")
        print(f"找到 {len(miz_files)} 个.miz文件")
        print("=" * 60)

        # Save config for next interactive session
        save_config({
            "api_key": args.api_key,
            "path": args.path,
            "only_chs": args.only_chs,
            "remove_json": args.remove_json,
            "use_remote_cache": use_remote,
        })

        transyytg_con(
            args.api_key, args.remove_json, args.path, args.only_chs,
            use_remote=use_remote
        )
    else:
        # Interactive mode
        interactive_mode()

    print("完成！")
    if sys.platform == "win32":
        os.system("pause")


if __name__ == "__main__":
    main()

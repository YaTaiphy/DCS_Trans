"""
Military Glossary — Dynamic Prompt Injection + Post-translation Correction

Two roles:
  1. BEFORE LLM call: scan source text, detect relevant glossary terms,
     build a targeted mini-prompt injected into the system message.
  2. AFTER LLM call: post-process translations to catch any remaining
     terminology errors (safety net for cached and fresh results).
"""

import os
import re
import json
import sys
import logging


# ---------------------------------------------------------------------------
# Glossary loading
# ---------------------------------------------------------------------------

_glossary_cache = None


def _find_glossary_path():
    """
    Resolve military_glossary.json path across environments:
      - Development (running from source)
      - Nuitka --standalone (folder with exe + bundled files)
      - Nuitka --onefile   (temp extraction dir, needs --include-data-files)

    Returns the first existing path, or the __file__-relative path as default.
    """
    candidates = []

    # 1) __file__-relative (dev + Nuitka with data files included)
    candidates.append(
        os.path.join(os.path.dirname(__file__), "military_glossary.json")
    )

    # 2) Executable-relative (Nuitka onefile fallback)
    if getattr(sys, 'frozen', False):
        # PyInstaller
        base = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
        candidates.append(os.path.join(base, "util", "military_glossary.json"))
    else:
        exe_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(exe_dir, "util", "military_glossary.json"))
        candidates.append(os.path.join(exe_dir, "military_glossary.json"))

    # 3) CWD-relative (last resort)
    candidates.append(os.path.join("util", "military_glossary.json"))
    candidates.append("military_glossary.json")

    for path in candidates:
        if os.path.exists(path):
            return path

    # Not found — return the primary path so the error message is clear
    return candidates[0]


def load_glossary():
    """Load the military glossary, cached in memory after first call."""
    global _glossary_cache
    if _glossary_cache is not None:
        return _glossary_cache

    path = _find_glossary_path()
    with open(path, "r", encoding="utf-8") as f:
        _glossary_cache = json.load(f)
    return _glossary_cache


# ---------------------------------------------------------------------------
# Regex helper (non-letter boundary, works with CJK unlike \\b)
# ---------------------------------------------------------------------------

_BOUNDARY_L = r'(?<![a-zA-Z])'
_BOUNDARY_R = r'(?![a-zA-Z])'


def _has_word(term, text):
    """Check if `term` appears as a whole word/phrase in `text`.

    Uses non-letter boundary lookarounds because Python 3 treats CJK
    characters as \\w in Unicode mode, so \\b does not fire between
    Chinese and English characters.
    """
    if " " in term or "-" in term or "/" in term:
        return term.lower() in text.lower()
    return bool(re.search(
        _BOUNDARY_L + re.escape(term) + _BOUNDARY_R, text, re.IGNORECASE
    ))


# ---------------------------------------------------------------------------
# Dynamic prompt builder (BEFORE LLM call)
# ---------------------------------------------------------------------------

def build_dynamic_glossary_prompt(json_data_filtered, glossary=None):
    """
    Scan translatable source text for glossary terms and build a targeted
    terminology appendix for the LLM system prompt.

    Only includes terms actually found in the current text, keeping the
    injected prompt lean (typically 100-500 chars).

    Args:
        json_data_filtered: {DictKey_xxx: "English source text"}
        glossary: Pre-loaded glossary dict (auto-loads if None)

    Returns:
        String to append to the system prompt, or "" if no terms found.
    """
    if glossary is None:
        glossary = load_glossary()

    # Combine all source text for scanning
    all_text = " ".join(json_data_filtered.values())

    keep_found = []       # (en_term, zh_hint) — terms to KEEP in English
    translate_found = []  # (en_term, zh_target) — terms to TRANSLATE

    for category, entries in glossary.items():
        if category.startswith("_"):
            continue

        for term, info in entries.items():
            policy = info.get("policy", "")
            zh = info.get("zh", "")

            if not zh or not _has_word(term, all_text):
                continue

            # Infer policy from category when not explicit
            if not policy:
                if category == "brevity_translate":
                    policy = "translate"
                elif category in ("weapon_codes", "threat_systems",
                                  "roles_and_platforms"):
                    policy = "keep"

            if policy == "keep":
                keep_found.append((term, zh))
            elif policy == "translate":
                translate_found.append((term, zh))

    if not keep_found and not translate_found:
        return ""

    lines = ["", "【本次翻译涉及的专业术语 — 严格遵守】"]

    if keep_found:
        lines.append("下列术语必须保留原文，不要翻译为中文：")
        for term, zh in sorted(set(keep_found)):
            lines.append(f"  {term} - 保留原文 (非 {zh})")

    if translate_found:
        lines.append("下列术语必须翻译为中文：")
        for term, zh in sorted(set(translate_found)):
            lines.append(f"  {term} → {zh}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Post-translation correction (AFTER LLM call — safety net)
# ---------------------------------------------------------------------------

def _build_maps(glossary):
    """Build keep_map and translate_map for post-processing correction."""
    keep_map = {}
    translate_map = {}

    for category, entries in glossary.items():
        if category.startswith("_"):
            continue

        for term, info in entries.items():
            policy = info.get("policy", "")
            zh = info.get("zh", "")

            if not zh:
                continue

            if not policy:
                if category == "brevity_translate":
                    policy = "translate"
                elif category in ("weapon_codes", "threat_systems",
                                  "roles_and_platforms"):
                    policy = "keep"

            if policy == "keep":
                keep_map[zh] = term
            elif policy == "translate":
                translate_map[term.lower()] = zh

    return keep_map, translate_map


def correct_translations(original_dict, translated_dict, glossary=None):
    """
    Post-process translations against the glossary to fix:

      Pass 1: "keep" terms incorrectly translated → revert to English
              e.g. "防空压制" → "SEAD"

      Pass 2: "translate" terms kept in English → apply Chinese
              e.g. "winchester" → "弹药耗尽"

    Runs on both cached and freshly-generated translations, acting as
    a safety net regardless of whether dynamic prompt injection was used.

    Args:
        original_dict:   {DictKey_xxx: "original English text"}
        translated_dict: {DictKey_xxx: "translated Chinese text"}
        glossary:        Pre-loaded glossary dict (auto-loads if None)

    Returns:
        Corrected translated_dict (new dict, input unchanged)
    """
    if glossary is None:
        glossary = load_glossary()

    keep_map, translate_map = _build_maps(glossary)
    if not keep_map and not translate_map:
        return dict(translated_dict)

    corrected = {}
    corrections_made = 0

    for key, original_en in original_dict.items():
        text = translated_dict.get(key, "")
        if not text:
            corrected[key] = text
            continue

        # --- Pass 1: revert "keep" terms translated to Chinese ---
        for zh_term, en_term in keep_map.items():
            if not _has_word(en_term, original_en):
                continue
            if en_term in text:
                continue  # already correct
            if zh_term in text:
                text = text.replace(zh_term, en_term)
                corrections_made += 1

        # --- Pass 2: apply "translate" terms kept in English ---
        for en_term_lower, zh_term in translate_map.items():
            if not _has_word(en_term_lower, original_en):
                continue
            if zh_term in text:
                continue  # already correct
            pattern = re.compile(
                _BOUNDARY_L + re.escape(en_term_lower) + _BOUNDARY_R,
                re.IGNORECASE
            )
            if pattern.search(text):
                text = pattern.sub(zh_term, text)
                corrections_made += 1

        corrected[key] = text

    if corrections_made:
        logging.info("Glossary corrections: %d fix(es)", corrections_made)
        from util.output import tlog
        tlog(f"  Glossary correction: {corrections_made} fix(es)")

    return corrected

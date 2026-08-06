"""
LLM Translation Client

Calls the DeepSeek API (via OpenAI-compatible SDK) for translation.
Uses the v4-pro model with high reasoning effort for best quality.
"""

from openai import OpenAI
import os
import json


def dptrans(text, api_key, base_url="https://api.deepseek.com",
            model="deepseek-chat",
            hint="你是一个翻译，下面是跟战斗机任务（DCS模拟飞行游戏）相关的英语，翻译成简体中文，不要使用markdown输出, 保持原文的换行格式，仅作为翻译不要续写，原文和翻译词数不能相差过大。"):
    """
    Simple single-text translation via DeepSeek API.
    Used for ad-hoc translations outside the main batch workflow.
    """
    client = OpenAI(api_key=api_key, base_url=base_url)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": hint},
            {"role": "user", "content": "翻译：\n" + text},
        ],
        stream=False
    )

    return response.choices[0].message.content


def LLM_trans_v2(system_prompt, input_text, api_key, CACHE_DIR, CONTENT_HASH):
    """
    Batch translation via DeepSeek v4 Pro with thinking mode enabled.

    Saves the raw LLM response to a debug file (separate from the parsed
    translation cache to avoid overwrite).

    Args:
        system_prompt: Full system prompt (static + dynamic glossary)
        input_text: Formatted input text with <input_id> tags
        api_key: DeepSeek API key
        CACHE_DIR: Local cache directory path
        CONTENT_HASH: Content hash for debug file naming

    Returns:
        Raw LLM response text (with <input_id> tags)
    """
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )

    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": input_text},
        ],
        stream=False,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}}
    )

    # Save raw response for debugging (separate from parsed cache)
    debug_path = os.path.join(CACHE_DIR, f"{CONTENT_HASH}_raw.txt")
    with open(debug_path, "w", encoding="utf-8") as f:
        f.write(response.choices[0].message.content)

    return response.choices[0].message.content


if __name__ == "__main__":
    result = dptrans("PLAYER: Ravens, comin' right, roll out 120.")
    print(result)

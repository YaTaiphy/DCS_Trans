"""
LLM Translation Client

Calls the DeepSeek API (via OpenAI-compatible SDK) for translation.
Uses the v4-pro model with high reasoning effort for best quality.

Includes timeout control and retry logic for robustness:
  - Timeout: 180s per call (single-file translation with thinking mode)
  - Retries: up to 3 attempts with exponential backoff (3s, 6s, 12s)
  - Retryable: timeout, connection error, 5xx, 429 (rate limit)
  - Non-retryable: 4xx (auth/bad request — retrying won't help)
"""

from openai import OpenAI, APITimeoutError, APIConnectionError, \
    APIStatusError, RateLimitError
import os
import json
import time

# ---------------------------------------------------------------------------
# Retry & timeout configuration
# ---------------------------------------------------------------------------
LLM_TIMEOUT = 180             # seconds per single API call
LLM_MAX_RETRIES = 3
LLM_RETRY_BACKOFF = (3, 6, 12)  # seconds between retries


def _backoff_wait(e, attempt):
    """
    Determine sleep duration for a retryable error.

    For RateLimitError (429), respects the Retry-After header if present;
    otherwise falls back to the static backoff schedule.
    """
    if isinstance(e, RateLimitError):
        wait = e.response.headers.get("Retry-After")
        if wait is not None:
            try:
                return float(wait)
            except ValueError:
                pass
    idx = min(attempt, len(LLM_RETRY_BACKOFF) - 1)
    return LLM_RETRY_BACKOFF[idx]


def _is_retryable(e):
    """Return True if the exception is worth retrying."""
    if isinstance(e, (APITimeoutError, APIConnectionError, RateLimitError)):
        return True
    if isinstance(e, APIStatusError) and e.status_code >= 500:
        return True
    return False


def dptrans(text, api_key, base_url="https://api.deepseek.com",
            model="deepseek-chat",
            hint="你是一个翻译，下面是跟战斗机任务（DCS模拟飞行游戏）相关的英语，翻译成简体中文，不要使用markdown输出, 保持原文的换行格式，仅作为翻译不要续写，原文和翻译词数不能相差过大。",
            timeout=LLM_TIMEOUT):
    """
    Simple single-text translation via DeepSeek API.
    Used for ad-hoc translations outside the main batch workflow.
    """
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": hint},
            {"role": "user", "content": "翻译：\n" + text},
        ],
        stream=False,
        timeout=timeout,
    )

    return response.choices[0].message.content


def LLM_trans_v2(system_prompt, input_text, api_key, CACHE_DIR, CONTENT_HASH,
                 timeout=LLM_TIMEOUT, max_retries=LLM_MAX_RETRIES):
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
        timeout: Seconds per call (default 180)
        max_retries: Max retry attempts (default 3)

    Returns:
        Raw LLM response text (with <input_id> tags)

    Raises:
        APITimeoutError if all retries exhausted on timeout
        APIStatusError  for non-retryable API errors
    """
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
        timeout=timeout,
    )

    last_err = None
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="deepseek-v4-pro",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": input_text},
                ],
                stream=False,
                reasoning_effort="low",
                extra_body={"thinking": {"type": "enabled"}},
                timeout=timeout,
            )

            # Save raw response for debugging
            debug_path = os.path.join(CACHE_DIR, f"{CONTENT_HASH}_raw.txt")
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(response.choices[0].message.content)

            return response.choices[0].message.content

        except Exception as e:
            last_err = e
            if not _is_retryable(e) or attempt + 1 >= max_retries:
                raise
            wait = _backoff_wait(e, attempt)
            print(f"  LLM 调用失败 (尝试 {attempt + 1}/{max_retries})，"
                  f"{wait:.0f}s 后重试: {e}")
            time.sleep(wait)

    # Should not reach here, but just in case
    raise last_err


if __name__ == "__main__":
    result = dptrans("PLAYER: Ravens, comin' right, roll out 120.")
    print(result)

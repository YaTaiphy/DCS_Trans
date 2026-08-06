"""
Remote Translation Cache Client

Communicates with the community translation cache server for
sharing translations across users. Uses MD5 content hash as
the lookup key.

Protocol:
    GET  /health              — Health check
    POST /looking_translated  — Look up a translation by hash
    POST /save_translated     — Save a translation by hash

Backward compatibility:
    The remote server API is unchanged — we send the raw MD5 hash
    (without algorithm prefix) since the server predates the v2
    naming convention. The prefix is only used for local file naming.
"""

import requests

IP_ADDRESS = "121.41.75.139"
PORT = 10386


def looking_translated(content_hash):
    """
    Query remote server for a cached translation.

    Args:
        content_hash: MD5 hex digest of the source content (32 hex chars)

    Returns:
        (found: bool, content: dict|str)
    """
    try:
        # Health check
        response = requests.get(
            f"http://{IP_ADDRESS}:{PORT}/health", timeout=5
        )
        if response.status_code != 200:
            return False, "Remote server unavailable"

        print("Remote server available, looking up translation...")
        response = requests.post(
            f"http://{IP_ADDRESS}:{PORT}/looking_translated",
            json={"mizNameBase16": content_hash},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return True, data.get("content")
            return False, data.get("message", "Unknown error")

    except requests.RequestException as e:
        print(f"Remote server request failed: {e}")

    return False, "Remote lookup not implemented"


def save_translated(content_hash, translated_content):
    """
    Save a translation result to the remote cache server.

    Args:
        content_hash: MD5 hex digest of the source content
        translated_content: Dict of key→translation mappings

    Returns:
        (success: bool, message: str)
    """
    try:
        response = requests.post(
            f"http://{IP_ADDRESS}:{PORT}/save_translated",
            json={
                "mizNameBase16": content_hash,
                "translatedContentJson": translated_content
            },
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return True, "Saved successfully"
            return False, data.get("message", "Unknown error")
    except requests.RequestException as e:
        print(f"Remote server request failed: {e}")

    return False, "Remote save not implemented"


if __name__ == "__main__":
    # Test lookup
    test_hash = "test_hash_value"
    found, content = looking_translated(test_hash)
    if found:
        print(f"Remote lookup success: {content}")
    else:
        print(f"Remote lookup failed: {content}")

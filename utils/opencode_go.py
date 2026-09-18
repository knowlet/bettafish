"""OpenCode Go request metadata helpers.

OpenCode Go requires external coding agents to send a stable x-opencode-session
header per conversation and recommends a distinct user-agent.
"""

from __future__ import annotations

import os
import uuid
from typing import Dict, Optional


_PROCESS_SESSION_ID = os.getenv("OPENCODE_SESSION_ID") or f"bettafish-{uuid.uuid4()}"


def is_opencode_go(base_url: Optional[str]) -> bool:
    if not base_url:
        return False
    return "opencode.ai/zen/go/" in base_url.rstrip("/") + "/"


def get_opencode_go_headers(base_url: Optional[str]) -> Dict[str, str]:
    """Return required/recommended OpenCode Go headers, or an empty dict."""
    if not is_opencode_go(base_url):
        return {}

    return {
        "x-opencode-session": _PROCESS_SESSION_ID,
        "User-Agent": os.getenv("OPENCODE_USER_AGENT", "bettafish/1.0"),
    }

"""Unified inference client for SGLang backend (OpenAI-compatible, KV cache reuse)."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

_client = None


def get_sglang_client(base_url: Optional[str] = None):
    """Get singleton OpenAI client configured for SGLang server."""
    global _client
    if _client is not None:
        return _client

    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package required: pip install openai")

    base_url = base_url or os.getenv("SGLANG_BASE_URL", "http://localhost:30000/v1")
    _client = OpenAI(base_url=base_url, api_key="EMPTY")
    return _client


def generate_completion(
    messages: List[Dict[str, str]],
    model: str,
    temperature: float = 0.3,
    max_tokens: int = 128,
    response_format: Optional[Dict[str, Any]] = None,
    client: Optional[Any] = None,
) -> str:
    """Generate a chat completion via SGLang server."""
    client = client or get_sglang_client()
    try:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        response = client.chat.completions.create(**payload)
        if not response.choices:
            raise ValueError("No choices in response")
        return response.choices[0].message.content or ""
    except Exception as e:
        raise RuntimeError(f"SGLang inference failed: {e}") from e

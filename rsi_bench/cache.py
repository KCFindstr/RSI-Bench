"""
Local response cache manager for RSI-Bench.
Allows caching LLM turn responses to disk to prevent duplicate calls and enable deterministic replay.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from rsi_bench.models import ProviderResponse, TokenUsage


class ResponseCache:
    """Persistent disk cache for LLM provider responses."""

    def __init__(self, cache_dir: str = ".rsi_cache", enabled: bool = True):
        self.enabled = enabled
        self.cache_dir = Path(cache_dir)
        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def compute_cache_key(
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        system_prompt: Optional[str] = None,
        extra_params: Optional[dict[str, Any]] = None,
    ) -> str:
        """Computes a deterministic SHA256 key based on request payload."""
        payload = {
            "provider": provider.lower(),
            "model": model,
            "messages": messages,
            "system_prompt": system_prompt,
            "extra_params": extra_params or {},
        }
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def get(self, cache_key: str) -> Optional[ProviderResponse]:
        """Retrieve a cached response if present."""
        if not self.enabled:
            return None

        file_path = self.cache_dir / f"{cache_key}.json"
        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            usage_data = data.get("usage", {})
            usage = TokenUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
                cached_tokens=usage_data.get("cached_tokens", 0),
                cache_creation_tokens=usage_data.get("cache_creation_tokens", 0),
                reasoning_tokens=usage_data.get("reasoning_tokens", 0),
            )

            metadata = data.get("metadata", {})
            metadata["from_local_cache"] = True

            return ProviderResponse(
                content=data.get("content", ""),
                thinking=data.get("thinking"),
                usage=usage,
                raw_request=data.get("raw_request"),
                raw_response=data.get("raw_response"),
                metadata=metadata,
            )
        except Exception:
            # If cache file is corrupt, treat as cache miss
            return None

    def set(self, cache_key: str, response: ProviderResponse) -> None:
        """Save a provider response to cache."""
        if not self.enabled:
            return

        file_path = self.cache_dir / f"{cache_key}.json"
        data = {
            "content": response.content,
            "thinking": response.thinking,
            "usage": response.usage.model_dump(),
            "raw_request": response.raw_request,
            "raw_response": response.raw_response,
            "metadata": response.metadata,
        }
        try:
            temp_path = self.cache_dir / f"{cache_key}.tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            temp_path.replace(file_path)
        except Exception:
            pass

    def clear(self) -> int:
        """Clear all cached entries."""
        if not self.cache_dir.exists():
            return 0
        count = 0
        for p in self.cache_dir.glob("*.json"):
            try:
                p.unlink()
                count += 1
            except Exception:
                pass
        return count

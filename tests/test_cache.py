"""Unit tests for the response cache layer."""

import tempfile
import pytest
from rsi_bench.cache import ResponseCache
from rsi_bench.models import ProviderResponse, TokenUsage


class TestResponseCache:
    def test_cache_set_and_get(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ResponseCache(cache_dir=tmpdir, enabled=True)
            key = cache.compute_cache_key(
                provider="anthropic",
                model="claude-3-7-sonnet",
                messages=[{"role": "user", "content": "Generate a random integer"}],
            )

            # Initially cache miss
            assert cache.get(key) is None

            resp = ProviderResponse(
                content="42",
                thinking="I thought about 42",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=5, cached_tokens=50),
                raw_request={"dummy": 1},
                raw_response={"dummy": 2},
                metadata={"foo": "bar"},
            )

            cache.set(key, resp)

            cached = cache.get(key)
            assert cached is not None
            assert cached.content == "42"
            assert cached.thinking == "I thought about 42"
            assert cached.usage.cached_tokens == 50
            assert cached.metadata["foo"] == "bar"
            assert cached.metadata["from_local_cache"] is True

    def test_cache_disabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ResponseCache(cache_dir=tmpdir, enabled=False)
            key = cache.compute_cache_key("openai", "gpt-4o", [])
            resp = ProviderResponse(content="123")
            cache.set(key, resp)
            assert cache.get(key) is None

    def test_cache_clear(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ResponseCache(cache_dir=tmpdir, enabled=True)
            key1 = cache.compute_cache_key("openai", "gpt-4o", [{"content": "turn1"}])
            key2 = cache.compute_cache_key("openai", "gpt-4o", [{"content": "turn2"}])

            cache.set(key1, ProviderResponse(content="1"))
            cache.set(key2, ProviderResponse(content="2"))

            count = cache.clear()
            assert count == 2
            assert cache.get(key1) is None
            assert cache.get(key2) is None

"""
Base provider abstraction for RSI-Bench.
Provides consistent interface, error handling, retry backoff, and tracing.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import httpx

from rsi_bench.models import BenchmarkConfig, Message, ProviderResponse, TokenUsage


class ProviderError(Exception):
    """Base exception for provider API failures."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class BaseProvider(ABC):
    """Abstract base class for all LLM providers."""

    def __init__(
        self,
        config: BenchmarkConfig,
        http_client: Optional[httpx.Client] = None,
    ):
        self.config = config
        self.client = http_client or httpx.Client(
            timeout=httpx.Timeout(self.config.timeout_seconds, connect=10.0),
            follow_redirects=True,
        )
        self._owns_client = http_client is None

    def close(self) -> None:
        """Close the underlying HTTP client if created internally."""
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> BaseProvider:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _execute_with_retry(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        json_body: Dict[str, Any],
        params: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Executes HTTP request with exponential backoff for rate limits and server errors."""
        max_retries = max(0, self.config.max_retries)
        last_error: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                response = self.client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_body,
                    params=params,
                )

                # Retry on rate limit (429) or transient server errors (500, 502, 503, 504)
                if response.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                    backoff = (2 ** attempt) + 0.5
                    time.sleep(backoff)
                    continue

                if response.is_error:
                    error_text = response.text
                    raise ProviderError(
                        f"Provider {self.config.provider} returned HTTP {response.status_code}: {error_text}",
                        status_code=response.status_code,
                        response_body=error_text,
                    )

                return response

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_error = e
                if attempt < max_retries:
                    time.sleep((2 ** attempt) + 0.5)
                    continue
                raise ProviderError(f"Network error communicating with {self.config.provider}: {e}") from e

        if last_error:
            raise ProviderError(f"Max retries exceeded for {self.config.provider}: {last_error}") from last_error

        raise ProviderError(f"Request failed after {max_retries} retries")

    @abstractmethod
    def send_turn(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
    ) -> ProviderResponse:
        """
        Send a conversation turn to the provider and return a standardized ProviderResponse.
        """
        pass

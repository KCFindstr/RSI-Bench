"""Pytest fixtures and mock transport helpers for RSI-Bench."""

import pytest
import httpx


@pytest.fixture
def mock_transport():
    """Helper to create custom httpx.MockTransport for provider tests."""
    def _create(handler):
        return httpx.Client(transport=httpx.MockTransport(handler))
    return _create

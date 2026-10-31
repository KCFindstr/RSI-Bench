import sys
from pathlib import Path
import pytest
import httpx

# Ensure RSI-Bench root directory is in sys.path
_pkg_root = str(Path(__file__).resolve().parent.parent)
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)


@pytest.fixture
def mock_transport():
    """Helper to create custom httpx.MockTransport for provider tests."""
    def _create(handler):
        return httpx.Client(transport=httpx.MockTransport(handler))
    return _create

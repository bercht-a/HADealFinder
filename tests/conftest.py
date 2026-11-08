"""Fixtures for Deal Finder tests."""

from __future__ import annotations

import sys

import pytest

if sys.platform == "win32":  # local dev only: the Windows event loop needs a socketpair
    import pytest_socket

    pytest_socket.disable_socket = lambda *args, **kwargs: None
    pytest_socket.socket_allow_hosts = lambda *args, **kwargs: None


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom_components in all tests."""
    return

"""Pytest configuration for the test suite."""

import pytest


def pytest_addoption(parser):
    """Add custom pytest options."""
    parser.addoption(
        "--run-embedding-tests",
        action="store_true",
        default=False,
        help="Run tests that require API key and make external calls",
    )


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "embedding: marks tests that require API key")
    config.addinivalue_line("markers", "smoke: marks tests as smoke tests (integration tests for deployed service)")

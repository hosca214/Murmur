import os
import tempfile
import pytest


@pytest.fixture
def tmp_app_support(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setenv("MURMUR_APP_SUPPORT", d)
        yield d

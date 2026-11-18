import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.data import load_appointments, load_fees  # noqa: E402


@pytest.fixture(autouse=True)
def no_api_key(monkeypatch):
    """Tests are offline and deterministic: always use the regex parser."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture
def fees():
    return load_fees()


@pytest.fixture
def appts():
    return {a.patient_id: a for a in load_appointments()}

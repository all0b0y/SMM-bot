import importlib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_smm_bot_package_imports_when_present() -> None:
    if not (ROOT / "src/smm_bot").exists():
        pytest.skip("smm_bot package is not present in this repository state")

    module = importlib.import_module("smm_bot")

    assert module.__name__ == "smm_bot"

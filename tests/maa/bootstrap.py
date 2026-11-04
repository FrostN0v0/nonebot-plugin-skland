"""Load the standalone MAA package without starting the Skland application."""

import sys
import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("nonebot.adapters.qq")

DIRECTORY = Path(__file__).resolve().parents[2] / "nonebot_plugin_skland/integrations/maa"
spec = importlib.util.spec_from_file_location(
    "maa", DIRECTORY / "__init__.py", submodule_search_locations=[str(DIRECTORY)]
)
module = importlib.util.module_from_spec(spec)
sys.modules["maa"] = module
spec.loader.exec_module(module)
sys.path.insert(0, str(DIRECTORY))
from maa import core

sys.modules["core"] = core

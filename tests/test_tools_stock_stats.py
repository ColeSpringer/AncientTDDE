"""The DAT snapshot tool's tree-screen cross-check finds every civilization's tree file."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("stock_stats", ROOT / "tools/dat/stock_stats.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tree(path: Path, statuses: dict[str, str]) -> None:
    nodes = [{"Name": name, "Node Status": status} for name, status in statuses.items()]
    path.write_text(json.dumps({"civs": [{"Nodes": nodes}]}), encoding="utf-8")


def test_tree_files_are_found_under_the_games_own_names(tool: ModuleType, tmp_path: Path) -> None:
    assert tool.tree_file("French") == "FRANKS"
    assert tool.tree_file("Hindustanis") == "INDIANS"
    assert tool.tree_file("Magyars") == "MAGYAR"
    assert tool.tree_file("Koreans") == "KOREANS"
    tree(tmp_path / "FRANKS.json", {"Guard Tower": "ResearchedCompleted", "Keep": "NotAvailable"})
    assert tool.tree_lacks(tmp_path, "French") == {"KEEP", "BOMBARD_TOWER"}


def test_a_missing_tree_file_is_reported_not_skipped(
    tool: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert tool.tree_lacks(tmp_path, "Atlanteans") is None
    assert "Atlanteans: no tree file ATLANTEANS.json" in capsys.readouterr().out

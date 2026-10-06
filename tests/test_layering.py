"""Each package imports only the layers beneath it, so the layers cannot tangle again."""

import ast
from pathlib import Path

import pytest

import ancienttdde
from ancienttdde.common.layers import ASSETS, IMPORTS, reachable

PACKAGE = Path(ancienttdde.__file__).resolve().parent
# The command line and `python -m ancienttdde` sit above every layer.
UNRESTRICTED = frozenset({"cli", "__main__"})
MODULES = sorted(PACKAGE.rglob("*.py"))


def layer(path: Path) -> str:
    return path.relative_to(PACKAGE).parts[0].removesuffix(".py")


def imported_layers(path: Path) -> set[str]:
    """Return the top-level ancienttdde modules a file imports, including lazy imports."""
    module = path.relative_to(PACKAGE).with_suffix("").parts
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = ".".join(("ancienttdde", *module[: len(module) - node.level]))
                target = f"{base}.{node.module}" if node.module else base
            else:
                target = node.module or ""
            if target == "ancienttdde":
                names.update(f"ancienttdde.{alias.name}" for alias in node.names)
            else:
                names.add(target)
    return {name.split(".")[1] for name in names if name.startswith("ancienttdde.")}


def module_id(path: Path) -> str:
    return path.relative_to(PACKAGE).as_posix()


def test_every_package_has_a_place_in_the_layer_table() -> None:
    assert {layer(path) for path in MODULES} <= IMPORTS.keys() | UNRESTRICTED


@pytest.mark.parametrize("path", MODULES, ids=module_id)
def test_modules_import_only_lower_layers(path: Path) -> None:
    own = layer(path)
    if own in UNRESTRICTED:
        return
    forbidden = imported_layers(path) - {own} - IMPORTS[own]
    assert not forbidden, f"{module_id(path)} ({own}) imports {sorted(forbidden)}"


def asset_names(path: Path) -> set[str]:
    """Return the assets a module reads with asset_text, which must name them literally."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        name = function.id if isinstance(function, ast.Name) else getattr(function, "attr", "")
        if name == "asset_text":
            [argument] = node.args
            assert isinstance(argument, ast.Constant) and isinstance(argument.value, str), (
                f"{module_id(path)} reads an asset by a computed name"
            )
            names.add(argument.value)
    return names


def test_each_layer_declares_the_assets_it_reads() -> None:
    read: dict[str, set[str]] = {}
    for path in MODULES:
        if names := asset_names(path):
            read.setdefault(layer(path), set()).update(names)
    assert read == {name: set(assets) for name, assets in ASSETS.items()}


def test_every_packaged_asset_belongs_to_a_layer() -> None:
    files = {path.name for path in (PACKAGE / "assets").iterdir()}
    assert files == {name for assets in ASSETS.values() for name in assets}


def test_a_layer_reaches_every_layer_its_imports_can_run() -> None:
    assert reachable("game") == {"game", "map", "scenario", "common", "models", "registry"}
    assert reachable("probes") == {"probes", "scenario", "common", "models", "registry"}
    with pytest.raises(ValueError, match="Unknown package layer: cli"):
        reachable("cli")

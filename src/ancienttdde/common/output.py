"""Keep generated output away from sources and publish it only once it is complete."""

from collections.abc import Iterable
from itertools import takewhile
from pathlib import Path

from ancienttdde.common.manifest import ManifestKind, read_kind

# Sources, immutable inputs and tool state; generated output never goes inside them.
PROTECTED = (
    "content",
    "legacy",
    "src",
    "tests",
    "tools",
    "typings",
    "docs",
    ".git",
    ".agents",
    ".codex",
    ".venv",
)


def project_path(root: Path, relative: str) -> Path:
    result = (root / relative).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError(f"Path is outside the project: {relative}")
    return result


def resolve_output(root: Path, output: Path | None, default: str) -> Path:
    """Resolve a directory outside the sources, the project itself and its ancestors, without
    creating it."""
    root = root.resolve()
    if output is None:
        # A configured default stays inside the project, though a directory there may link
        # to another disk.
        relative = Path(default)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(
                f"Default output must be a relative path inside the project: {default}"
            )
        output = root / relative
    directory = output.resolve()
    if root.is_relative_to(directory) or any(
        directory.is_relative_to((root / name).resolve()) for name in PROTECTED
    ):
        raise ValueError("Output must be outside source directories and their ancestors")
    if directory.exists() and not directory.is_dir():
        raise ValueError("Output must be a directory")
    return directory


def artifact_folders(directory: Path, names: Iterable[str]) -> set[Path]:
    """The folders between the output directory and its nested artifacts."""
    return {
        folder
        for name in names
        for folder in takewhile(lambda path: path != directory, (directory / name).parents)
    }


def prepare_output(
    root: Path, output: Path | None, default: str, names: Iterable[str], *, kind: ManifestKind
) -> Path:
    """Resolve a directory the pipeline may write, without creating it.

    An existing directory belongs to the pipeline whose kind its manifest declares,
    whatever the manifest's schema; validation parses the complete manifest.
    """
    directory = resolve_output(root, output, default)
    owned = (*names, "manifest.json")
    folders = artifact_folders(directory, owned)
    if any(path.is_symlink() for path in (*(directory / name for name in owned), *folders)):
        raise ValueError("Output cannot replace artifact symlinks or their folders")
    if any(folder.exists() and not folder.is_dir() for folder in folders):
        raise ValueError("Output has a file where an artifact folder goes")
    if (directory / "manifest.json").exists():
        try:
            owner = read_kind(directory / "manifest.json")
        except ValueError:
            owner = None
        if owner != kind:
            raise ValueError("Output contains an unrelated manifest; choose another output")
    elif any((directory / name).exists() for name in owned):
        raise ValueError("Output cannot overwrite unrelated artifacts")
    return directory


def publish(staging: Path, directory: Path, names: Iterable[str]) -> None:
    """Move staged artifacts into place, creating every folder first and the manifest last."""
    owned = (*names, "manifest.json")
    for name in owned:
        (directory / name).parent.mkdir(parents=True, exist_ok=True)
    for name in owned:
        (staging / name).replace(directory / name)

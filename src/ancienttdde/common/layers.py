"""The package's layers, the layers each may import, and the assets each reads."""

# tests/test_layering.py holds every module to these imports, so a layer and the layers it
# may import, directly or through one another, contain all the code it can run.
IMPORTS: dict[str, frozenset[str]] = {
    "__init__": frozenset(),
    "models": frozenset(),
    "registry": frozenset({"models"}),
    "common": frozenset({"models"}),
    "scenario": frozenset({"common", "models", "registry"}),
    "map": frozenset({"scenario", "common", "models", "registry"}),
    "audit": frozenset({"scenario", "common", "models", "registry"}),
    "game": frozenset({"map", "scenario", "common", "models", "registry"}),
    "probes": frozenset({"scenario", "common", "models", "registry"}),
}

# The files in the package's assets directory that each layer reads with asset_text.
ASSETS: dict[str, tuple[str, ...]] = {
    "scenario": ("passive.per",),
    "game": ("runtime.xs",),
    "probes": ("probe-heartbeat.xs", "probe-raider-purchases.xs"),
}


def reachable(layer: str) -> frozenset[str]:
    """Return the layer and every layer it may import, directly or through another."""
    if layer not in IMPORTS:
        raise ValueError(f"Unknown package layer: {layer}")
    found = {layer}
    pending = [layer]
    while pending:
        for name in IMPORTS[pending.pop()] - found:
            found.add(name)
            pending.append(name)
    return frozenset(found)

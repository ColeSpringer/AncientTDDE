# Immutable legacy inputs

The original package is Ancient TD v5.3 Drag Tower Mod (WORKING), credited in
`original/info.json` to **DRAX6869**; the scenario credits **DRAX**.
`original.zip` is the supplied archive and `original/` is its extracted content.
Neither the archive, extracted package nor the generated DAT references belong
in the modern gameplay release. They are intentionally ignored by Git.

`provenance.json` records SHA-256 hashes and sizes for the supplied archive,
every extracted file, both C++ genieutils reference snapshots and the
modern format seed. Paths are relative to the repository root. The audit checks
these hashes before reading any sources. The original binary DAT is authoritative;
reference JSON is a derived representation, never an editable balance file.

To work from a fresh checkout, supply the original archive and extracted files at
the recorded paths, then supply the verified reference dump or regenerate it with
`tools/dat/dump_legacy_dat.sh`. Regeneration requires the matching genieutils
version and produces a new derived snapshot; compare it with the recorded hashes
before intentionally updating provenance. Do not edit the original package.

The zero-byte `reference/dat-json/ancient-td.json` is an abandoned partial-export
path. It is not an audit input. See `docs/legacy-dat.md` for the usable full export.

The supplied `reference/dat/` snapshot has corrupted French and Cumans JSON.
It is preserved for provenance. `reference/dat-verified/` was regenerated from
the original DAT and is the audit input; the exporter validated every section.

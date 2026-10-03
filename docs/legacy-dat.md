## Legacy Ancient TD data

The original Ancient TD v5.3 binary data mod `44262_Ancient TD v5.3 Drag Tower Mod (WORKING)/` is under "legacy/original"

For legacy `.dat` questions, use `legacy/reference/dat-verified/manifest.json` and the
JSON files it references first. This is a comprehensive introspection dump of
the `VER 7.4` / `GV_C17` DAT parsed by C++ genieutils.

Do not edit the generated JSON by hand. Regenerate it with:

`./tools/dat/dump_legacy_dat.sh`

The original `.dat` is the byte-level source of truth. The JSON is the preferred
human/agent-readable representation.

The supplied `legacy/reference/dat/` export is retained unchanged. Its French
and Cumans JSON contain structural corruption; the verified export was
regenerated separately using genieutils commit
`02baa4cc16e5e9e00425a0a1821f3b242cd9655d`. Both snapshots and the source DAT
are hashed in `legacy/provenance.json`.

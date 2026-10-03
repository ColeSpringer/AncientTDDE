# Legacy DAT full dump

This replaces the earlier hand-written partial TSV dump.

It loads the Ancient TD `VER 7.4` / `GV_C17` DAT with the C++ `genieutils`
library and uses GDB's C++ debug-type information to recursively export the
parsed data model. This avoids maintaining a manual list of every Unit,
Building, Combat, Graphic, Effect, Terrain, etc. field.

## Dependencies

```bash
sudo apt install -y g++ gdb
```

GDB must have Python support and the libstdc++ pretty-printers installed.
The C++ `genieutils` checkout, including its headers and built
`build/libgenieutils.so`, is expected at:

```text
~/dev/tools/genieutils
```

Override with `GENIEUTILS=/some/path` if necessary.

## Run

From the AncientTDDE repo root:

```bash
chmod +x tools/dat/dump_legacy_dat.sh
./tools/dat/dump_legacy_dat.sh
```

Default input:

```text
legacy/original/resources/_common/dat/empires2_x2_p1.dat
```

Default output:

```text
legacy/reference/dat-verified/
```

You can override both:

```bash
./tools/dat/dump_legacy_dat.sh /path/to/input.dat /path/to/output
```

Defaults are resolved relative to the script's repository, so the launcher
also works when invoked by its absolute path from another directory. Explicit
relative arguments are resolved against the current working directory.
Use `--help` for usage. The loader targets `VER 7.4` / `GV_C17`; supplying another
input path does not automatically select another game version.

## Output

`manifest.json` is the entry point. Large civilization/unit data is split into
one JSON file per civilization; the other major DAT sections are separate JSON
files.

The dump includes every ordinary data member visible in the C++ parsed model,
including nested structures and data-bearing base classes. Static members,
`ISerializable`, and `IFile` runtime bookkeeping are excluded because those are
parser implementation state. C++ strings become JSON strings, including empty
strings, Unicode, and embedded null characters.
Vectors and fixed-size `std::array` members become JSON arrays. For
`std::array`, the exporter can read the libstdc++ storage directly on systems
without an array pretty-printer.

Each section is checked for conversion errors before it is written, and
non-finite numbers are rejected to keep the output valid JSON. Errors stop the
command with a nonzero exit status and include the affected file/member path
when available. Progress appears as each section and civilization is processed.
Undecodable strings and missing required pretty-printers also fail explicitly.

The export is built in a temporary directory next to the destination. Only a
complete export replaces the previous output; failures leave the previous
output intact. Replacement removes stale files from earlier exports, so use a
dedicated output directory. The launcher rejects a file or symlink destination,
or a directory containing the input DAT, repository, build directory, or tools.

The original binary DAT remains the byte-level source of truth.

## Validation

The first milestone regenerated a complete snapshot using this exporter. The
supplied `legacy/reference/dat/` directory is retained unchanged because its
French and Cumans JSON contain structural corruption. Provenance records both
snapshots and the original binary; the audit uses `dat-verified/`.

`uv run pytest` includes synthetic DAT inspection tests. GDB export requires
permission to debug the loader child (`ptrace`) and a compatible genieutils build.
There is no `tools/dat/tests` directory in this checkout.

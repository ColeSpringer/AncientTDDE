"""Export parsed DAT values from a stopped GDB inferior as JSON."""

# Pretty-printers can raise arbitrary Python exceptions. Preserve their context
# in conversion markers, then reject those markers before writing an export.
# ruff: noqa: BLE001

import json
import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol, cast

# GDB supplies this module inside its embedded Python interpreter.
import gdb  # pyright: ignore[reportMissingModuleSource]

type JSONValue = str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]


class PrettyPrinter(Protocol):
    """Printer methods used here; missing methods are handled by the callers."""

    def children(self) -> Iterator[tuple[str, gdb.Value]]: ...

    def to_string(
        self,
    ) -> str | gdb.LazyString | gdb.Value | int | float | bool | None: ...


SKIP_BASES = {"genie::ISerializable", "genie::IFile"}

SCALARS = [
    "FileVersion",
    "TimeSlice",
    "UnitKillRate",
    "UnitKillTotal",
    "UnitHitPointRate",
    "UnitHitPointTotal",
    "RazingKillRate",
    "RazingKillTotal",
    "TerrainsUsed1",
    "SUnknown2",
    "SUnknown3",
    "swgbBlendModes",
    "swgbMaxBlendmodes",
    "SUnknown7",
    "SUnknown8",
]

SECTIONS = [
    ("float_ptr_terrain_tables.json", "FloatPtrTerrainTables"),
    ("terrain_pass_graphic_pointers.json", "TerrainPassGraphicPointers"),
    ("terrain_restrictions.json", "TerrainRestrictions"),
    ("player_colours.json", "PlayerColours"),
    ("sounds.json", "Sounds"),
    ("graphic_pointers.json", "GraphicPointers"),
    ("graphics.json", "Graphics"),
    ("terrain_block.json", "TerrainBlock"),
    ("random_maps.json", "RandomMaps"),
    ("effects.json", "Effects"),
    ("unit_headers.json", "UnitHeaders"),
    ("technologies.json", "Techs"),
    ("unit_lines.json", "UnitLines"),
    ("tech_tree.json", "TechTree"),
]


def exposed(name: str) -> gdb.Value:
    return gdb.parse_and_eval(f"*::g_{name}")


def safe_name(s: str | None) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s or "")
    return s.strip("._")[:80] or "unnamed"


def pp(value: gdb.Value) -> PrettyPrinter | None:
    try:
        # GDB's stubs omit children() and some valid to_string() return types.
        return cast(PrettyPrinter | None, gdb.default_visualizer(value))
    except Exception:
        return None


def pp_children(value: gdb.Value) -> list[tuple[str, gdb.Value]] | None:
    p = pp(value)
    if p is None:
        return None
    try:
        return list(p.children())
    except Exception:
        return None


def pp_text(value: gdb.Value) -> str | dict[str, JSONValue] | None:
    p = pp(value)
    if p is None:
        return None
    try:
        x = p.to_string()
        if isinstance(x, gdb.LazyString):
            # LazyString.value() still returns a GDB value, not Python text.
            return x.value().string(encoding=x.encoding or "", length=x.length)
        return None if x is None else str(x)
    except Exception as error:
        return {"__error__": str(error)}


def convert(value: gdb.Value, depth: int = 0) -> JSONValue:
    if depth > 128:
        return {"__error__": "maximum recursion depth reached"}

    typ = value.type.strip_typedefs()
    name = str(typ)
    code = typ.code

    if code == gdb.TYPE_CODE_REF:
        try:
            return convert(value.referenced_value(), depth + 1)
        except Exception as e:
            return {"__reference_error__": str(e)}

    if code == gdb.TYPE_CODE_PTR:
        try:
            addr = int(value)
            return None if addr == 0 else {"__pointer__": hex(addr)}
        except Exception:
            return str(value)

    if code == gdb.TYPE_CODE_BOOL:
        return bool(int(value))
    if code in (gdb.TYPE_CODE_INT, gdb.TYPE_CODE_CHAR, gdb.TYPE_CODE_RANGE):
        return int(value)
    if code == gdb.TYPE_CODE_FLT:
        return float(value)
    if code == gdb.TYPE_CODE_ENUM:
        try:
            return {"value": int(value), "name": str(value)}
        except Exception:
            return str(value)

    if code == gdb.TYPE_CODE_ARRAY:
        try:
            lo, hi = typ.range()
            return [convert(value[i], depth + 1) for i in range(lo, hi + 1)]
        except Exception as e:
            return {"__array_error__": str(e)}

    if name.startswith(("std::basic_string<", "std::__cxx11::basic_string<")) or name in (
        "std::string",
        "std::__cxx11::string",
    ):
        txt = pp_text(value)
        if txt is not None:
            return txt
        return {"__error__": f"No GDB string pretty-printer for {name}"}

    children = pp_children(value)

    if name.startswith("std::array<"):
        if children is not None:
            return [convert(v, depth + 1) for _, v in children]
        try:
            # libstdc++ has no array printer on some GDB versions. Its empty
            # array uses an empty struct instead of a zero-length C array.
            # This non-type argument is a Value; GDB's stubs only list Type.
            size = cast(gdb.Value, typ.template_argument(1))
            if int(size) == 0:
                return []
            return convert(value["_M_elems"], depth + 1)
        except Exception as error:
            return {"__array_error__": str(error)}

    seq = (
        "std::vector<",
        "std::deque<",
        "std::list<",
        "std::forward_list<",
    )
    if name.startswith(seq):
        if children is None:
            return {"__error__": f"No GDB sequence pretty-printer for {name}"}
        return [convert(v, depth + 1) for _, v in children]

    if name.startswith("std::pair<") and children is not None:
        vals = list(children)
        if len(vals) >= 2:
            return {
                "first": convert(vals[0][1], depth + 1),
                "second": convert(vals[1][1], depth + 1),
            }

    if (
        name.startswith(("std::optional<", "std::shared_ptr<", "std::unique_ptr<"))
        and children is not None
    ):
        vals = list(children)
        if not vals:
            return None
        if len(vals) == 1:
            return convert(vals[0][1], depth + 1)
        return {str(k): convert(v, depth + 1) for k, v in vals}

    if name.startswith(("std::map<", "std::unordered_map<")) and children is not None:
        vals = list(children)
        entries: list[JSONValue] = []
        i = 0
        while i < len(vals):
            if i + 1 < len(vals):
                entries.append(
                    {
                        "key": convert(vals[i][1], depth + 1),
                        "value": convert(vals[i + 1][1], depth + 1),
                    }
                )
                i += 2
            else:
                entries.append(convert(vals[i][1], depth + 1))
                i += 1
        return entries

    if code in (gdb.TYPE_CODE_STRUCT, gdb.TYPE_CODE_UNION):
        result: dict[str, JSONValue] = {}
        try:
            fields = typ.fields()
        except Exception as e:
            return {"__type__": name, "__error__": str(e)}

        if not fields:
            return {"__type__": name, "__error__": "no debug fields available"}

        for field in fields:
            try:
                if field.is_base_class:
                    base_type = field.type
                    if base_type is None:
                        raise ValueError("Base class has no type information")
                    base_name = str(base_type.strip_typedefs())
                    if base_name in SKIP_BASES:
                        continue
                    base_data = convert(value.cast(base_type), depth + 1)
                    if isinstance(base_data, dict):
                        for k, v in base_data.items():
                            if k not in result:
                                result[k] = v
                            else:
                                result[f"__base_{safe_name(base_name)}__{k}"] = v
                    else:
                        result[f"__base_{safe_name(base_name)}"] = base_data
                    continue

                # Static members have no bit position in an object instance.
                if getattr(field, "bitpos", None) is None or not field.name:
                    continue
                result[field.name] = convert(value[field], depth + 1)
            except Exception as e:
                result[field.name or "<anonymous>"] = {"__error__": str(e)}
        return result

    if children is not None:
        return {str(k): convert(v, depth + 1) for k, v in children}

    txt = pp_text(value)
    if txt is not None:
        return txt

    return {"__unsupported_type__": name, "__value__": str(value)}


def check_conversion(value: JSONValue, location: str) -> None:
    """Reject error placeholders so a partial dump cannot look successful."""
    if isinstance(value, dict):
        for key in (
            "__error__",
            "__reference_error__",
            "__array_error__",
            "__unsupported_type__",
        ):
            if key in value:
                raise ValueError(f"{location}: {key}: {value[key]}")
        for key, item in value.items():
            check_conversion(item, f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            check_conversion(item, f"{location}[{index}]")


def dump_json(path: Path, obj: JSONValue) -> None:
    check_conversion(obj, str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write("\n")


def vector_elements(value: gdb.Value) -> list[gdb.Value]:
    children = pp_children(value)
    if children is None:
        raise RuntimeError(f"No GDB pretty-printer for {value.type}")
    return [v for _, v in children]


def main() -> None:
    out = Path(os.environ["DAT_DUMP_OUT"])
    out.mkdir(parents=True, exist_ok=True)

    # Scalars / metadata
    meta: dict[str, JSONValue] = {}
    for name in SCALARS:
        try:
            meta[name] = convert(exposed(name))
        except Exception as e:
            meta[name] = {"__error__": str(e)}
    dump_json(out / "meta.json", meta)

    exported_files: list[JSONValue] = ["meta.json"]
    manifest: dict[str, JSONValue] = {
        "format": "genieutils-gdb-introspection-v4",
        "source_file_version": meta.get("FileVersion"),
        "game_version": "GV_C17",
        "files": exported_files,
        "notes": [
            "Generated from a fully parsed legacy DAT using C++ genieutils.",
            "Top-level DAT members are exposed as dedicated globals to avoid "
            "GDB DatFile member-lookup issues.",
            "The loader is compiled with -femit-class-debug-always so nested "
            "genieutils classes retain field metadata.",
            "ISerializable and IFile runtime bookkeeping are intentionally excluded.",
            "The original DAT remains the byte-level source of truth.",
        ],
    }

    # Major sections
    for filename, name in SECTIONS:
        print(f"Dumping {name} -> {filename}", flush=True)
        dump_json(out / filename, convert(exposed(name)))
        exported_files.append(filename)

    # Civs are split because each contains its own large unit table.
    print("Dumping Civs -> civilizations/*.json", flush=True)
    civs_dir = out / "civilizations"
    civs_dir.mkdir(parents=True, exist_ok=True)

    civ_index: list[JSONValue] = []
    civs = vector_elements(exposed("Civs"))
    for i, civ in enumerate(civs):
        print(f"  civilization {i + 1}/{len(civs)}", flush=True)
        data = convert(civ)
        name = data.get("Name", f"civ_{i}") if isinstance(data, dict) else f"civ_{i}"
        if not isinstance(name, str):
            name = str(name)

        filename = f"{i:03d}_{safe_name(name)}.json"
        dump_json(civs_dir / filename, data)
        civ_index.append(
            {
                "index": i,
                "name": name,
                "file": f"civilizations/{filename}",
            }
        )

    dump_json(out / "civilizations.json", civ_index)
    exported_files.extend(["civilizations.json", "civilizations/"])
    dump_json(out / "manifest.json", manifest)

    print("All sections exported and validated.", flush=True)


if __name__ == "__main__":
    main()

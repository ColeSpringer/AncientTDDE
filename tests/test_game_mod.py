"""The description and thumbnail DE's Mod Center reads from the generated mod folder."""

import json
from pathlib import Path

import pytest

from ancienttdde.game.mod import load_description, load_thumbnail, mod_info

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_END = b"\x00\x00\x00\x00IEND\xaeB`\x82"
PNG = PNG_SIGNATURE + PNG_END
JPEG = b"\xff\xd8\xff\xe0" + b"\0" * 12
FACTS = {"lanes": 7, "waves": 56, "bosses": 10, "population": 200}


def test_the_description_is_the_single_line_of_its_file(tmp_path: Path) -> None:
    path = tmp_path / "description.txt"
    path.write_text("Fixed Ancient TD v5.3.\n", encoding="utf-8")
    assert load_description(path, FACTS) == "Fixed Ancient TD v5.3."


def test_a_byte_order_mark_is_not_part_of_the_description(tmp_path: Path) -> None:
    path = tmp_path / "description.txt"
    path.write_text("Fixed Ancient TD v5.3.\n", encoding="utf-8-sig")
    assert load_description(path, FACTS) == "Fixed Ancient TD v5.3."


@pytest.mark.parametrize(
    "text",
    [
        "",
        "  \n",
        "One line.\nAnother line.\n",
        "Windows\r\nbreak\n",
        "One two",
        "One\x85two",
        "One\x0btwo",
        "One\x0ctwo",
    ],
)
def test_an_empty_or_multi_line_description_is_rejected(tmp_path: Path, text: str) -> None:
    path = tmp_path / "description.txt"
    path.write_text(text, encoding="utf-8", newline="")
    with pytest.raises(ValueError, match="one line of text"):
        load_description(path, FACTS)


def test_the_description_fills_in_the_game_numbers(tmp_path: Path) -> None:
    path = tmp_path / "description.txt"
    path.write_text(
        "1 to {lanes} players, {waves} waves, {bosses} bosses, Population {population}.\n",
        encoding="utf-8",
    )
    assert load_description(path, FACTS) == "1 to 7 players, 56 waves, 10 bosses, Population 200."


@pytest.mark.parametrize("text", ["{towers} towers", "{} waves", "a { brace"])
def test_a_description_with_an_unknown_placeholder_is_rejected(tmp_path: Path, text: str) -> None:
    path = tmp_path / "description.txt"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="placeholder"):
        load_description(path, FACTS)


def test_the_mod_info_is_de_compact_json_with_the_author_left_to_de() -> None:
    text = mod_info('A line with "quotes" and é.')
    assert text == (
        '{"Author":"","CacheStatus":0,"Description":"A line with \\"quotes\\" and é.",'
        '"Title":"Ancient TD DE"}'
    )
    assert json.loads(text) == {
        "Author": "",
        "CacheStatus": 0,
        "Description": 'A line with "quotes" and é.',
        "Title": "Ancient TD DE",
    }


def test_a_png_thumbnail_is_read_as_is(tmp_path: Path) -> None:
    path = tmp_path / "thumbnail.png"
    path.write_bytes(PNG)
    assert load_thumbnail(path) == PNG


@pytest.mark.parametrize("data", [JPEG, PNG_SIGNATURE + b"\0" * 8, PNG[:-1]])
def test_a_thumbnail_that_is_not_a_complete_png_is_rejected(tmp_path: Path, data: bytes) -> None:
    path = tmp_path / "thumbnail.png"
    path.write_bytes(data)
    with pytest.raises(ValueError, match="PNG"):
        load_thumbnail(path)

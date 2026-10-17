"""
Unit tests for pure-Python debim/YAML parser (debim_ingetrazo/parser.py).
"""

import pytest
from debim_ingetrazo.parser import parse_debim_str, parse_scalar, parse_debim


def test_parse_scalar():
    assert parse_scalar("123") == 123
    assert parse_scalar("-45") == -45
    assert parse_scalar("3.14159") == 3.14159
    assert parse_scalar("true") is True
    assert parse_scalar("FALSE") is False
    assert parse_scalar("null") is None
    assert parse_scalar('"hello world"') == "hello world"
    assert parse_scalar("'single quoted'") == "single quoted"
    assert parse_scalar("[1, 2, 3]") == [1, 2, 3]
    assert parse_scalar("['a', 'b', 'c']") == ["a", "b", "c"]
    assert parse_scalar("{a: 1, b: 2}") == {"a": 1, "b": 2}


def test_parse_simple_mapping():
    yaml_text = """
    project:
      name: Sample Project
      units: m
      version: 1.0
    """
    res = parse_debim_str(yaml_text)
    assert res["project"]["name"] == "Sample Project"
    assert res["project"]["units"] == "m"
    assert res["project"]["version"] == 1.0


def test_parse_nested_storeys_and_entities():
    yaml_text = """
    project:
      name: Multi-Storey Building
      units: m
      origin: [0, 0, 0]

    building:
      name: Main Tower
      storeys:
        - id: LEVEL_1
          name: Ground Floor
          elevation: 0.0
          height: 3.5
          slabs:
            - id: SLAB_1
              thickness: 0.25
              boundary: [[0, 0], [10, 0], [10, 8], [0, 8]]
          walls:
            - id: WALL_1
              start: [0, 0]
              end: [10, 0]
              thickness: 0.2
              height: 3.5
              openings:
                - id: DOOR_1
                  offset: 2.0
                  width: 1.0
                  height: 2.1
          columns:
            - id: COL_1
              position: [0, 0]
              section: [0.4, 0.4]
        - id: LEVEL_2
          name: First Floor
          elevation: 3.5
          height: 3.0
    """
    res = parse_debim_str(yaml_text)
    assert res["project"]["name"] == "Multi-Storey Building"
    assert res["project"]["origin"] == [0, 0, 0]

    storeys = res["building"]["storeys"]
    assert len(storeys) == 2
    assert storeys[0]["id"] == "LEVEL_1"
    assert storeys[0]["elevation"] == 0.0
    assert storeys[0]["height"] == 3.5

    slabs = storeys[0]["slabs"]
    assert len(slabs) == 1
    assert slabs[0]["id"] == "SLAB_1"
    assert slabs[0]["boundary"] == [[0, 0], [10, 0], [10, 8], [0, 8]]

    walls = storeys[0]["walls"]
    assert len(walls) == 1
    assert walls[0]["id"] == "WALL_1"
    assert len(walls[0]["openings"]) == 1
    assert walls[0]["openings"][0]["id"] == "DOOR_1"


def test_parse_comments_and_empty_lines():
    yaml_text = """
    # Project configuration comment
    project: # Inline comment
      name: "Commented Test" # another comment
      count: 42
    """
    res = parse_debim_str(yaml_text)
    assert res["project"]["name"] == "Commented Test"
    assert res["project"]["count"] == 42


def test_parse_file_not_found():
    with pytest.raises(FileNotFoundError):
        parse_debim("non_existent_file.debim")

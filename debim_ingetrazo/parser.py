"""
Pure-Python lightweight YAML / .debim manifest parser with zero external dependencies.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Union, Tuple, Optional


def _strip_comment(line: str) -> str:
    """Strip trailing # comment from line, respecting quotes."""
    in_quote = None
    escaped = False
    for i, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char in ('"', "'"):
            if in_quote is None:
                in_quote = char
            elif in_quote == char:
                in_quote = None
        elif char == "#" and in_quote is None:
            return line[:i]
    return line


def parse_scalar(val: str) -> Any:
    """Parse scalar value into int, float, bool, None, list, dict, or string."""
    val = val.strip()
    if not val:
        return None

    # Quoted strings
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1]

    # Booleans
    val_lower = val.lower()
    if val_lower in ("true", "yes", "on"):
        return True
    if val_lower in ("false", "no", "off"):
        return False
    if val_lower in ("null", "none", "~"):
        return None

    # Inline List [a, b, c]
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        items = _split_inline_sequence(inner)
        return [parse_scalar(item) for item in items]

    # Inline Dict {a: b, c: d}
    if val.startswith("{") and val.endswith("}"):
        inner = val[1:-1].strip()
        if not inner:
            return {}
        items = _split_inline_sequence(inner)
        res = {}
        for item in items:
            if ":" in item:
                k, v = item.split(":", 1)
                res[parse_scalar(k)] = parse_scalar(v)
        return res

    # Integer
    try:
        if val.startswith("0x") or val.startswith("0X"):
            return int(val, 16)
        return int(val)
    except ValueError:
        pass

    # Float
    try:
        return float(val)
    except ValueError:
        pass

    return val


def _split_inline_sequence(text: str) -> List[str]:
    """Split comma-separated inline items respecting quotes and brackets."""
    items = []
    current = []
    in_quote = None
    bracket_depth = 0
    brace_depth = 0

    for char in text:
        if char in ('"', "'"):
            if in_quote is None:
                in_quote = char
            elif in_quote == char:
                in_quote = None
            current.append(char)
        elif in_quote is not None:
            current.append(char)
        elif char == '[':
            bracket_depth += 1
            current.append(char)
        elif char == ']':
            bracket_depth -= 1
            current.append(char)
        elif char == '{':
            brace_depth += 1
            current.append(char)
        elif char == '}':
            brace_depth -= 1
            current.append(char)
        elif char == ',' and bracket_depth == 0 and brace_depth == 0:
            items.append(''.join(current).strip())
            current = []
        else:
            current.append(char)

    if current:
        items.append(''.join(current).strip())

    return [item for item in items if item]


class _Line:
    def __init__(self, indent: int, content: str, original_line_no: int):
        self.indent = indent
        self.content = content
        self.line_no = original_line_no


def _preprocess_lines(text: str) -> List[_Line]:
    lines = []
    for idx, raw_line in enumerate(text.splitlines(), start=1):
        stripped = _strip_comment(raw_line)
        if not stripped.strip():
            continue
        indent = len(raw_line) - len(raw_line.lstrip(' '))
        content = stripped.strip()
        lines.append(_Line(indent, content, idx))
    return lines


def _parse_block(lines: List[_Line], start_idx: int, parent_indent: int) -> Tuple[Any, int]:
    """
    Recursively parse lines starting at start_idx with indent > parent_indent.
    Returns (parsed_structure, next_index).
    """
    if start_idx >= len(lines):
        return None, start_idx

    first_line = lines[start_idx]
    if first_line.indent <= parent_indent:
        return None, start_idx

    current_indent = first_line.indent
    is_sequence = first_line.content.startswith("-")

    if is_sequence:
        seq_result: List[Any] = []
        idx = start_idx

        while idx < len(lines):
            line = lines[idx]
            if line.indent < current_indent:
                break
            if line.indent > current_indent:
                # Handled inside item processing
                pass

            if line.content.startswith("-"):
                item_str = line.content[1:].strip()
                idx += 1

                if not item_str:
                    # Item content is on subsequent indented lines
                    if idx < len(lines) and lines[idx].indent > line.indent:
                        sub_val, idx = _parse_block(lines, idx, line.indent)
                        seq_result.append(sub_val)
                    else:
                        seq_result.append(None)
                elif ":" in item_str and not _is_quoted_or_inline(item_str):
                    # - key: value format
                    key_part, val_part = item_str.split(":", 1)
                    key = parse_scalar(key_part)
                    item_dict: Dict[Any, Any] = {}

                    val_part_stripped = val_part.strip()
                    if val_part_stripped:
                        item_dict[key] = parse_scalar(val_part_stripped)
                    else:
                        if idx < len(lines) and lines[idx].indent > line.indent:
                            sub_val, idx = _parse_block(lines, idx, line.indent)
                            item_dict[key] = sub_val
                        else:
                            item_dict[key] = None

                    # Collect additional keys for this sequence item dict
                    while idx < len(lines):
                        next_line = lines[idx]
                        if next_line.indent <= line.indent:
                            break
                        if next_line.content.startswith("-"):
                            break
                        if ":" in next_line.content and not _is_quoted_or_inline(next_line.content):
                            k_part, v_part = next_line.content.split(":", 1)
                            sub_key = parse_scalar(k_part)
                            idx += 1
                            v_part_str = v_part.strip()
                            if v_part_str:
                                item_dict[sub_key] = parse_scalar(v_part_str)
                            else:
                                if idx < len(lines) and lines[idx].indent > next_line.indent:
                                    sub_v, idx = _parse_block(lines, idx, next_line.indent)
                                    item_dict[sub_key] = sub_v
                                else:
                                    item_dict[sub_key] = None
                        else:
                            break

                    seq_result.append(item_dict)
                else:
                    seq_result.append(parse_scalar(item_str))
            else:
                break

        return seq_result, idx

    else:
        # Mapping dict
        dict_result: Dict[Any, Any] = {}
        idx = start_idx

        while idx < len(lines):
            line = lines[idx]
            if line.indent < current_indent:
                break

            if ":" in line.content and not _is_quoted_or_inline(line.content):
                k_part, v_part = line.content.split(":", 1)
                key = parse_scalar(k_part)
                idx += 1
                v_str = v_part.strip()

                if v_str:
                    dict_result[key] = parse_scalar(v_str)
                else:
                    if idx < len(lines) and lines[idx].indent > line.indent:
                        sub_val, idx = _parse_block(lines, idx, line.indent)
                        dict_result[key] = sub_val
                    else:
                        dict_result[key] = None
            else:
                idx += 1

        return dict_result, idx


def _is_quoted_or_inline(text: str) -> bool:
    """Check if the text is wrapped entirely in quotes or brackets/braces."""
    text = text.strip()
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return True
    if (text.startswith('[') and text.endswith(']')) or (text.startswith('{') and text.endswith('}')):
        return True
    return False


def parse_debim_str(text: str) -> Dict[str, Any]:
    """
    Parse `.debim` or YAML string content into a Python dict.
    """
    lines = _preprocess_lines(text)
    if not lines:
        return {}

    parsed, _ = _parse_block(lines, 0, -1)
    if isinstance(parsed, dict):
        return parsed
    elif parsed is None:
        return {}
    else:
        return {"data": parsed}


def parse_debim_file(filepath: Union[str, Path]) -> Dict[str, Any]:
    """
    Parse a `.debim` file path into a Python dict.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    return parse_debim_str(content)


parse_debim = parse_debim_file


def is_ifc_minimal_schema(data: Dict[str, Any]) -> bool:
    """
    Check if the parsed manifest dict conforms to the IFC4-Minimal debim CLI schema.
    """
    if not isinstance(data, dict):
        return False
    schema = data.get("schema")
    if isinstance(schema, str) and "ifc4" in schema.lower():
        return True
    if "elements" in data or "grids" in data:
        return True
    return False


def extract_elements(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract all element dictionaries from a parsed manifest, combining top-level
    `elements` as well as storey-level elements/simplified entities.
    """
    if not isinstance(data, dict):
        return []

    elements: List[Dict[str, Any]] = []

    # 1. Top-level elements
    top_elements = data.get("elements")
    if isinstance(top_elements, list):
        for elem in top_elements:
            if isinstance(elem, dict):
                elements.append(elem)

    # 2. Storey-level elements / simplified entities
    spatial = data.get("spatial_structure") or {}
    storeys = (
        spatial.get("storeys")
        or spatial.get("building", {}).get("storeys")
        or data.get("building", {}).get("storeys")
        or data.get("storeys")
        or []
    )

    if isinstance(storeys, list):
        for st in storeys:
            if not isinstance(st, dict):
                continue
            st_id = st.get("id") or st.get("name")

            # Standard storey elements list
            st_elements = st.get("elements")
            if isinstance(st_elements, list):
                for elem in st_elements:
                    if isinstance(elem, dict):
                        elem_copy = dict(elem)
                        if st_id and "storey" not in elem_copy and "placement" not in elem_copy:
                            elem_copy["storey"] = st_id
                        elements.append(elem_copy)

            # Simplified entities: slabs, walls, columns, beams, footings, roofs
            for category in ("slabs", "walls", "columns", "beams", "footings", "roofs"):
                cat_items = st.get(category)
                if isinstance(cat_items, list):
                    for item in cat_items:
                        if isinstance(item, dict):
                            item_copy = dict(item)
                            if "category" not in item_copy:
                                item_copy["category"] = category
                            if st_id and "storey" not in item_copy and "placement" not in item_copy:
                                item_copy["storey"] = st_id
                            elements.append(item_copy)

    return elements

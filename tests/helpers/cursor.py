"""Extract a Python string offset from a marked source fixture."""


def extract_cursor_offset(*, text_with_cursor: str) -> tuple[str, int]:
    marker = "<CURSOR>"
    if text_with_cursor.count(marker) != 1:
        raise ValueError("Expected exactly one <CURSOR> marker in the source fixture")
    offset = text_with_cursor.index(marker)
    return text_with_cursor.replace(marker, "", 1), offset

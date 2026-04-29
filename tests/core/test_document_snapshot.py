from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from q2lsp.core.document import DocumentSnapshot, OffsetMapper


def test_document_snapshot_is_immutable() -> None:
    snapshot = DocumentSnapshot(uri="file:///workflow.sh", text="qiime info", version=1)

    with pytest.raises(FrozenInstanceError):
        snapshot.text = "changed"  # type: ignore[misc]


def test_offset_mapper_round_trips_ascii_position() -> None:
    mapper = OffsetMapper("qiime\ninfo")

    position = mapper.offset_to_position(8)


    assert position == (1, 2)
    assert mapper.position_to_offset(*position) == 8


def test_offset_mapper_uses_utf16_lsp_columns() -> None:
    mapper = OffsetMapper("a😀b")


    assert mapper.offset_to_position(2) == (0, 3)
    assert mapper.position_to_offset(0, 3) == 2


def test_offset_mapper_handles_crlf_as_single_line_break() -> None:
    mapper = OffsetMapper("qiime\r\ninfo")

    position = mapper.offset_to_position(8)

    assert position == (1, 1)
    assert mapper.position_to_offset(*position) == 8


def test_offset_mapper_clamps_crlf_line_columns_before_line_break() -> None:
    mapper = OffsetMapper("qiime\r\ninfo")

    assert mapper.offset_to_position(5) == (0, 5)
    assert mapper.position_to_offset(0, 999) == 5


def test_offset_mapper_maps_crlf_boundary_offsets_to_end_of_line() -> None:
    mapper = OffsetMapper("qiime\r\ninfo")

    assert mapper.offset_to_position(5) == (0, 5)
    assert mapper.offset_to_position(6) == (0, 5)
    assert mapper.offset_to_position(7) == (1, 0)


def test_offset_mapper_maps_cr_boundary_offsets_to_end_of_line() -> None:
    mapper = OffsetMapper("abc\rdef")

    assert mapper.offset_to_position(3) == (0, 3)
    assert mapper.offset_to_position(4) == (1, 0)


def test_offset_mapper_clamps_cr_line_columns_before_line_break() -> None:
    mapper = OffsetMapper("abc\rdef")

    assert mapper.position_to_offset(0, 999) == 3

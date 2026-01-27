"""Tests for offset mapping in diagnostics.

Tests the merge_line_continuations offset_map to ensure
diagnostic issues are correctly mapped back to original offsets.
"""

from __future__ import annotations

from q2lsp.lsp.parser import merge_line_continuations


def map_merged_offset_to_original(merged_offset: int, offset_map: list[int]) -> int:
    """
    Map a merged offset back to the original offset.

    Args:
        merged_offset: Offset in the merged text.
        offset_map: Offset map from merge_line_continuations.

    Returns:
        The corresponding offset in the original text.
    """
    # offset_map[i] gives the original offset for merged position i
    if merged_offset < 0:
        raise ValueError("merged_offset must be non-negative")
    if merged_offset >= len(offset_map):
        raise ValueError("merged_offset exceeds offset_map size")
    return offset_map[merged_offset]


class TestOffsetMap:
    def test_simple_line_continuation(self) -> None:
        """Test offset mapping for a simple line continuation."""
        text = "qiime \\\nfeature-table summarize"
        merged_text, offset_map = merge_line_continuations(text)

        # merged_text should be "qiime feature-table summarize" (no backslash+newline)
        assert merged_text == "qiime feature-table summarize"

        # The offset_map should have length len(merged_text) + 1
        assert len(offset_map) == len(merged_text) + 1

        # Position 0 in merged text corresponds to position 0 in original
        assert map_merged_offset_to_original(0, offset_map) == 0

        # Position after "qiime " in merged corresponds to after "qiime \\\n" in original
        qiime_space_offset = merged_text.index("qiime ") + len("qiime ")
        assert map_merged_offset_to_original(qiime_space_offset, offset_map) == len(
            "qiime \\\n"
        )

        # Position of "f" in "feature-table" maps to position after continuation
        feature_table_offset = merged_text.index("feature-table")
        assert map_merged_offset_to_original(feature_table_offset, offset_map) == len(
            "qiime \\\n"
        )

        # End of merged text maps to end of original text
        assert map_merged_offset_to_original(len(merged_text), offset_map) == len(text)

    def test_issue_span_mapping(self) -> None:
        """Test that issue spans map correctly back to original offsets."""
        text = "qiime \\\nfeature-tabel summarize"
        merged_text, offset_map = merge_line_continuations(text)

        # Issue is at "feature-tabel" (typo)
        # Use merged_text.index to find the token position
        token_text = "feature-tabel"
        merged_start = merged_text.index(token_text)
        merged_end = merged_start + len(token_text)

        # Map back to original offsets
        original_start = map_merged_offset_to_original(merged_start, offset_map)
        original_end = map_merged_offset_to_original(merged_end, offset_map)

        # In original: "feature-tabel" is on line 2, starts at 8 (after "qiime \\\n")
        assert original_start == len("qiime \\\n")
        assert original_end == len("qiime \\\n") + len(token_text)

    def test_multiple_continuations(self) -> None:
        """Test offset mapping with multiple line continuations."""
        text = "qiime \\\nfeature-table \\\nsummarize"
        merged_text, offset_map = merge_line_continuations(text)

        assert merged_text == "qiime feature-table summarize"

        # "qiime" ends at position 5 in merged, also at 5 in original
        qiime_end_offset = merged_text.index("qiime") + len("qiime")
        assert (
            map_merged_offset_to_original(qiime_end_offset, offset_map)
            == qiime_end_offset
        )

        # "feature-table" starts at 6 in merged, at 8 in original (after "qiime \\\n")
        feature_table_offset = merged_text.index("feature-table")
        assert map_merged_offset_to_original(feature_table_offset, offset_map) == len(
            "qiime \\\n"
        )

        # "summarize" starts at 21 in merged, at 34 in original (after "qiime \\\nfeature-table \\\n")
        summarize_offset = merged_text.index("summarize")
        assert map_merged_offset_to_original(summarize_offset, offset_map) == len(
            "qiime \\\nfeature-table \\\n"
        )

        # End of text maps correctly
        assert map_merged_offset_to_original(len(merged_text), offset_map) == len(text)

    def test_no_continuation(self) -> None:
        """Test offset mapping when there are no line continuations."""
        text = "qiime feature-table summarize"
        merged_text, offset_map = merge_line_continuations(text)

        assert merged_text == text
        assert len(offset_map) == len(text) + 1

        # All offsets should map 1:1
        for i in range(len(text) + 1):
            assert map_merged_offset_to_original(i, offset_map) == i

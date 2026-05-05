"""Tests for offset mapping in diagnostics.

Tests the merge_line_continuations offset_map to ensure
diagnostic issues are correctly mapped back to original offsets.
"""

from __future__ import annotations

from q2lsp.lsp.document_commands import analyze_document, to_original_offset


class TestOffsetMap:
    def test_simple_line_continuation(self) -> None:
        """Test offset mapping for a simple line continuation."""
        text = "qiime \\\nfeature-table summarize"
        doc = analyze_document(text)

        # merged_text should be "qiime feature-table summarize" (no backslash+newline)
        assert doc.merged_text == "qiime feature-table summarize"

        # The offset_map should have length len(merged_text) + 1
        assert len(doc.offset_map) == len(doc.merged_text) + 1

        # Position 0 in merged text corresponds to position 0 in original
        assert to_original_offset(doc, 0) == 0

        # Position after "qiime " in merged corresponds to after "qiime \\\n" in original
        qiime_space_offset = doc.merged_text.index("qiime ") + len("qiime ")
        assert to_original_offset(doc, qiime_space_offset) == len("qiime \\\n")

        # Position of "f" in "feature-table" maps to position after continuation
        feature_table_offset = doc.merged_text.index("feature-table")
        assert to_original_offset(doc, feature_table_offset) == len("qiime \\\n")

        # End of merged text maps to end of original text
        assert to_original_offset(doc, len(doc.merged_text)) == len(text)

    def test_issue_span_mapping(self) -> None:
        """Test that issue spans map correctly back to original offsets."""
        text = "qiime \\\nfeature-tabel summarize"
        doc = analyze_document(text)

        # Issue is at "feature-tabel" (typo)
        # Use merged_text.index to find the token position
        token_text = "feature-tabel"
        merged_start = doc.merged_text.index(token_text)
        merged_end = merged_start + len(token_text)

        # Map back to original offsets
        original_start = to_original_offset(doc, merged_start)
        original_end = to_original_offset(doc, merged_end)

        # In original: "feature-tabel" is on line 2, starts at 8 (after "qiime \\\n")
        assert original_start == len("qiime \\\n")
        assert original_end == len("qiime \\\n") + len(token_text)

    def test_multiple_continuations(self) -> None:
        """Test offset mapping with multiple line continuations."""
        text = "qiime \\\nfeature-table \\\nsummarize"
        doc = analyze_document(text)

        assert doc.merged_text == "qiime feature-table summarize"

        # "qiime" ends at position 5 in merged, also at 5 in original
        qiime_end_offset = doc.merged_text.index("qiime") + len("qiime")
        assert to_original_offset(doc, qiime_end_offset) == qiime_end_offset

        # "feature-table" starts at 6 in merged, at 8 in original (after "qiime \\\n")
        feature_table_offset = doc.merged_text.index("feature-table")
        assert to_original_offset(doc, feature_table_offset) == len("qiime \\\n")

        # "summarize" starts at 21 in merged, at 34 in original (after "qiime \\\nfeature-table \\\n")
        summarize_offset = doc.merged_text.index("summarize")
        assert to_original_offset(doc, summarize_offset) == len(
            "qiime \\\nfeature-table \\\n"
        )

        # End of text maps correctly
        assert to_original_offset(doc, len(doc.merged_text)) == len(text)

    def test_no_continuation(self) -> None:
        """Test offset mapping when there are no line continuations."""
        text = "qiime feature-table summarize"
        doc = analyze_document(text)

        assert doc.merged_text == text
        assert len(doc.offset_map) == len(text) + 1

        # All offsets should map 1:1
        for i in range(len(text) + 1):
            assert to_original_offset(doc, i) == i

    def test_span_after_multiple_continuations(self) -> None:
        """Test span mapping after multiple continued lines."""
        text = "qiime \\\nfeature-table \\\nsumarize"
        doc = analyze_document(text)

        token_text = "sumarize"
        merged_start = doc.merged_text.index(token_text)
        merged_end = merged_start + len(token_text)

        assert to_original_offset(doc, merged_start) == len(
            "qiime \\\nfeature-table \\\n"
        )
        assert to_original_offset(doc, merged_end) == len(text)

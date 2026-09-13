"""Tests for unified diagnostics collection and document-level diagnostics."""

from __future__ import annotations

import pytest

import q2lsp.lsp.diagnostics.codes as diagnostic_codes
from q2lsp.lsp.diagnostics import collect_diagnostics
from q2lsp.lsp.diagnostics.codes import DEPENDENCY_CYCLE
from q2lsp.lsp.diagnostics.command_analysis import analyze_command
from q2lsp.lsp.document_commands import (
    analyze_document,
    to_original_offset,
)
from q2lsp.qiime.catalog import QiimeCatalog


@pytest.fixture
def dependency_hierarchy() -> dict:
    return {
        "qiime": {
            "name": "qiime",
            "builtins": ["tools"],
            "tools": {
                "name": "tools",
                "type": "builtin",
                "export": {
                    "name": "export",
                    "signature": [
                        {"name": "input_path", "type": "path"},
                        {"name": "output_path", "type": "path"},
                    ],
                },
            },
            "demo": {
                "name": "demo",
                "step": {
                    "name": "step",
                    "signature": [
                        {"name": "table", "type": "input"},
                        {"name": "result", "type": "output"},
                        {"name": "metadata", "type": "metadata", "default": None},
                        {"name": "threads", "type": "parameter", "default": 1},
                    ],
                },
            },
        }
    }


def test_command_issues_precede_document_issues(dependency_hierarchy: dict) -> None:
    document = analyze_document(
        "qiime demo step --i-table in.qza --o-result shared.qza --bad\n"
        "qiime demo step --i-table in.qza --o-result shared.qza"
    )
    issues = collect_diagnostics(
        document, QiimeCatalog.from_hierarchy(dependency_hierarchy)
    )
    assert [issue.code for issue in issues] == [
        diagnostic_codes.UNKNOWN_OPTION,
        diagnostic_codes.DUPLICATE_OUTPUT_PATH,
        diagnostic_codes.DUPLICATE_OUTPUT_PATH,
    ]


def test_command_dependencies_use_grouped_options_and_inline_values(
    dependency_hierarchy: dict,
) -> None:
    source = (
        "qiime tools export --input-path=in.qza --output-path out-dir "
        "--p-threads 4 --m-metadata-file meta.tsv"
    )
    document = analyze_document(source)

    dependencies = analyze_command(
        document.commands[0],
        QiimeCatalog.from_hierarchy(dependency_hierarchy),
        document.merged_text,
    ).dependencies

    input_start = source.index("in.qza")
    output_start = source.index("out-dir")

    assert len(dependencies.inputs) == 1
    assert len(dependencies.outputs) == 1
    assert dependencies.inputs[0].path == "in.qza"
    assert dependencies.inputs[0].start == input_start
    assert dependencies.inputs[0].end == input_start + len("in.qza")
    assert dependencies.outputs[0].path == "out-dir"
    assert dependencies.outputs[0].start == output_start
    assert dependencies.outputs[0].end == output_start + len("out-dir")


def test_command_dependencies_trim_inline_quoted_value_span(
    dependency_hierarchy: dict,
) -> None:
    source = 'qiime demo step --i-table="a.qza" --o-result out.qza'
    document = analyze_document(source)

    dependencies = analyze_command(
        document.commands[0],
        QiimeCatalog.from_hierarchy(dependency_hierarchy),
        document.merged_text,
    ).dependencies

    input_start = source.index("a.qza")

    assert len(dependencies.inputs) == 1
    assert dependencies.inputs[0].path == "a.qza"
    assert dependencies.inputs[0].start == input_start
    assert dependencies.inputs[0].end == input_start + len("a.qza")


def test_collect_diagnostics_detects_two_command_cycle(
    dependency_hierarchy: dict,
) -> None:
    source = "\n".join(
        [
            "qiime demo step --i-table b.qza --o-result a.qza",
            "qiime demo step --i-table a.qza --o-result b.qza",
        ]
    )
    document = analyze_document(source)

    issues = collect_diagnostics(
        document, QiimeCatalog.from_hierarchy(dependency_hierarchy)
    )
    cycle_issues = [issue for issue in issues if issue.code == DEPENDENCY_CYCLE]

    assert len(cycle_issues) == 2
    assert {issue.message for issue in cycle_issues} == {
        "Dependency cycle detected for input path 'a.qza'.",
        "Dependency cycle detected for input path 'b.qza'.",
    }


def test_collect_diagnostics_reports_duplicate_o_output_paths(
    dependency_hierarchy: dict,
) -> None:
    source = "\n".join(
        [
            "qiime demo step --i-table in-1.qza --o-result dup.qza",
            "qiime demo step --i-table in-2.qza --o-result dup.qza",
        ]
    )
    document = analyze_document(source)

    issues = collect_diagnostics(
        document, QiimeCatalog.from_hierarchy(dependency_hierarchy)
    )
    duplicate_issues = [
        issue
        for issue in issues
        if issue.code == diagnostic_codes.DUPLICATE_OUTPUT_PATH
    ]

    first_start = source.index("dup.qza")
    second_start = source.rindex("dup.qza")

    assert len(duplicate_issues) == 2
    assert {issue.message for issue in duplicate_issues} == {
        "Duplicate output path 'dup.qza' is produced by multiple commands.",
    }
    assert {(issue.start, issue.end) for issue in duplicate_issues} == {
        (first_start, first_start + len("dup.qza")),
        (second_start, second_start + len("dup.qza")),
    }


def test_collect_diagnostics_reports_duplicate_output_path_option(
    dependency_hierarchy: dict,
) -> None:
    source = "\n".join(
        [
            "qiime tools export --input-path in-1.qza --output-path dup-dir",
            "qiime tools export --input-path in-2.qza --output-path dup-dir",
        ]
    )
    document = analyze_document(source)

    issues = collect_diagnostics(
        document, QiimeCatalog.from_hierarchy(dependency_hierarchy)
    )
    duplicate_issues = [
        issue
        for issue in issues
        if issue.code == diagnostic_codes.DUPLICATE_OUTPUT_PATH
    ]

    first_start = source.index("dup-dir")
    third_start = source.rindex("dup-dir")

    assert len(duplicate_issues) == 2
    assert {(issue.start, issue.end) for issue in duplicate_issues} == {
        (first_start, first_start + len("dup-dir")),
        (third_start, third_start + len("dup-dir")),
    }
    assert all(
        issue.message
        == "Duplicate output path 'dup-dir' is produced by multiple commands."
        for issue in duplicate_issues
    )


def test_collect_diagnostics_skips_help_commands_for_duplicate_output_detection(
    dependency_hierarchy: dict,
) -> None:
    source = "\n".join(
        [
            "qiime demo step --help --o-result dup.qza",
            "qiime demo step --i-table in-2.qza --o-result dup.qza",
        ]
    )
    document = analyze_document(source)

    issues = collect_diagnostics(
        document, QiimeCatalog.from_hierarchy(dependency_hierarchy)
    )

    assert [
        issue
        for issue in issues
        if issue.code == diagnostic_codes.DUPLICATE_OUTPUT_PATH
    ] == []


def test_collect_diagnostics_anchors_duplicate_output_on_value_token(
    dependency_hierarchy: dict,
) -> None:
    source = "\n".join(
        [
            'qiime demo step --i-table in-1.qza --o-result="dup.qza"',
            "qiime demo step --i-table in-2.qza --o-result dup.qza",
        ]
    )
    document = analyze_document(source)

    issues = collect_diagnostics(
        document, QiimeCatalog.from_hierarchy(dependency_hierarchy)
    )
    duplicate_issues = [
        issue
        for issue in issues
        if issue.code == diagnostic_codes.DUPLICATE_OUTPUT_PATH
    ]

    assert len(duplicate_issues) == 2
    first_issue = min(duplicate_issues, key=lambda issue: issue.start)
    assert first_issue.start == source.index("dup.qza")
    assert first_issue.end == source.index("dup.qza") + len("dup.qza")


def test_collect_diagnostics_reports_duplicate_outputs_alongside_dependency_cycles(
    dependency_hierarchy: dict,
) -> None:
    source = "\n".join(
        [
            "qiime demo step --i-table in-1.qza --o-result shared.qza",
            "qiime demo step --i-table shared.qza --o-result shared.qza",
        ]
    )
    document = analyze_document(source)

    issues = collect_diagnostics(
        document, QiimeCatalog.from_hierarchy(dependency_hierarchy)
    )

    duplicate_issues = [
        issue
        for issue in issues
        if issue.code == diagnostic_codes.DUPLICATE_OUTPUT_PATH
    ]
    cycle_issues = [issue for issue in issues if issue.code == DEPENDENCY_CYCLE]

    assert len(duplicate_issues) == 2
    assert len(cycle_issues) == 1
    assert (
        cycle_issues[0].message
        == "Dependency cycle detected for input path 'shared.qza'."
    )


def test_collect_diagnostics_deduplicates_same_command_duplicate_output_path(
    dependency_hierarchy: dict,
) -> None:
    source = "\n".join(
        [
            (
                "qiime tools export --input-path in-1.qza --output-path dup-dir "
                "--output-path dup-dir"
            ),
            "qiime tools export --input-path in-2.qza --output-path dup-dir",
        ]
    )
    document = analyze_document(source)

    issues = collect_diagnostics(
        document, QiimeCatalog.from_hierarchy(dependency_hierarchy)
    )
    duplicate_issues = [
        issue
        for issue in issues
        if issue.code == diagnostic_codes.DUPLICATE_OUTPUT_PATH
    ]

    first_start = source.index("dup-dir")
    third_start = source.rindex("dup-dir")

    assert len(duplicate_issues) == 2
    assert {(issue.start, issue.end) for issue in duplicate_issues} == {
        (first_start, first_start + len("dup-dir")),
        (third_start, third_start + len("dup-dir")),
    }


def test_collect_diagnostics_detects_three_command_cycle(
    dependency_hierarchy: dict,
) -> None:
    source = "\n".join(
        [
            "qiime demo step --i-table c.qza --o-result a.qza",
            "qiime demo step --i-table a.qza --o-result b.qza",
            "qiime demo step --i-table b.qza --o-result c.qza",
        ]
    )
    document = analyze_document(source)

    issues = collect_diagnostics(
        document, QiimeCatalog.from_hierarchy(dependency_hierarchy)
    )
    cycle_issues = [issue for issue in issues if issue.code == DEPENDENCY_CYCLE]

    assert len(cycle_issues) == 3
    assert {issue.message for issue in cycle_issues} == {
        "Dependency cycle detected for input path 'a.qza'.",
        "Dependency cycle detected for input path 'b.qza'.",
        "Dependency cycle detected for input path 'c.qza'.",
    }


def test_collect_diagnostics_reports_self_loop_on_input_value_span(
    dependency_hierarchy: dict,
) -> None:
    source = "qiime demo step --i-table loop.qza --o-result loop.qza"
    document = analyze_document(source)

    issues = collect_diagnostics(
        document, QiimeCatalog.from_hierarchy(dependency_hierarchy)
    )
    cycle_issues = [issue for issue in issues if issue.code == DEPENDENCY_CYCLE]

    start = source.index("loop.qza")

    assert len(cycle_issues) == 1
    assert (
        cycle_issues[0].message
        == "Dependency cycle detected for input path 'loop.qza'."
    )
    assert cycle_issues[0].start == start
    assert cycle_issues[0].end == start + len("loop.qza")


def test_collect_diagnostics_skips_help_commands_for_cycle_detection(
    dependency_hierarchy: dict,
) -> None:
    source = "qiime demo step --help --i-table loop.qza --o-result loop.qza"
    document = analyze_document(source)

    issues = collect_diagnostics(
        document, QiimeCatalog.from_hierarchy(dependency_hierarchy)
    )

    assert [issue for issue in issues if issue.code == DEPENDENCY_CYCLE] == []


def test_collect_diagnostics_ignores_invalid_dependency_like_options(
    dependency_hierarchy: dict,
) -> None:
    source = "\n".join(
        [
            "qiime demo step --i-tabel b.qza --o-result a.qza",
            "qiime demo step --i-table a.qza --o-result b.qza",
        ]
    )
    document = analyze_document(source)

    issues = collect_diagnostics(
        document, QiimeCatalog.from_hierarchy(dependency_hierarchy)
    )

    assert [issue for issue in issues if issue.code == DEPENDENCY_CYCLE] == []
    unknown_option_issues = [
        issue for issue in issues if issue.code == "q2lsp-dni/unknown-option"
    ]
    assert len(unknown_option_issues) == 1
    assert "--i-tabel" in unknown_option_issues[0].message


def test_collect_diagnostics_maps_cycle_input_span_across_line_continuations(
    dependency_hierarchy: dict,
) -> None:
    source = "\n".join(
        [
            "qiime demo step \\",
            "  --i-table b.qza \\",
            "  --o-result a.qza",
            "qiime demo step --i-table a.qza --o-result b.qza",
        ]
    )
    document = analyze_document(source)

    issues = collect_diagnostics(
        document, QiimeCatalog.from_hierarchy(dependency_hierarchy)
    )
    cycle_issues = [issue for issue in issues if issue.code == DEPENDENCY_CYCLE]

    first_input_start = source.index("b.qza")
    matching_issue = next(
        issue
        for issue in cycle_issues
        if to_original_offset(document, issue.start) == first_input_start
    )

    assert to_original_offset(document, matching_issue.start) == first_input_start
    assert to_original_offset(document, matching_issue.end) == first_input_start + len(
        "b.qza"
    )

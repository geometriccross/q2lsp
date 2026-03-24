"""Tests for unified diagnostics collection and dependency cycles."""

from __future__ import annotations

import pytest

from q2lsp.lsp.diagnostics import collect_diagnostics
from q2lsp.lsp.diagnostics.codes import DEPENDENCY_CYCLE
from q2lsp.lsp.diagnostics.command_level import extract_command_dependencies
from q2lsp.lsp.diagnostics.diagnostic_issue import DiagnosticIssue
from q2lsp.lsp.diagnostics.models import CommandAnalysis, CommandDependencies
from q2lsp.lsp.document_commands import (
    AnalyzedDocument,
    analyze_document,
    to_original_offset,
)
from q2lsp.lsp.types import ParsedCommand, TokenSpan


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


def test_collect_diagnostics_runs_command_level_before_document_level(mocker) -> None:
    cmd1 = ParsedCommand(tokens=[TokenSpan("qiime", 0, 5)], start=0, end=5)
    cmd2 = ParsedCommand(tokens=[TokenSpan("qiime", 6, 11)], start=6, end=11)
    document = AnalyzedDocument(merged_text="", offset_map=(0,), commands=(cmd1, cmd2))

    issue1 = DiagnosticIssue("command-1", 0, 1, "code-1")
    issue2 = DiagnosticIssue("command-2", 1, 2, "code-2")
    document_issue = DiagnosticIssue("document", 2, 3, "code-3")

    call_order: list[tuple[str, object]] = []

    analyses = [
        CommandAnalysis(
            command=cmd1,
            issues=(issue1,),
            dependencies=CommandDependencies(),
        ),
        CommandAnalysis(
            command=cmd2,
            issues=(issue2,),
            dependencies=CommandDependencies(),
        ),
    ]

    def fake_analyze_command(
        command: ParsedCommand, hierarchy: dict, source_text: str
    ) -> CommandAnalysis:
        del hierarchy, source_text
        call_order.append(("command", command))
        return analyses[len(call_order) - 1]

    def fake_collect_document_diagnostics(
        command_analyses: tuple[CommandAnalysis, ...],
    ) -> list[DiagnosticIssue]:
        call_order.append(("document", command_analyses))
        return [document_issue]

    mocker.patch(
        "q2lsp.lsp.diagnostics.collector.analyze_command",
        side_effect=fake_analyze_command,
    )
    mocker.patch(
        "q2lsp.lsp.diagnostics.collector.collect_document_diagnostics",
        side_effect=fake_collect_document_diagnostics,
    )

    issues = collect_diagnostics(document, {"qiime": {}})

    assert issues == [issue1, issue2, document_issue]
    assert call_order == [
        ("command", cmd1),
        ("command", cmd2),
        ("document", tuple(analyses)),
    ]


def test_extract_command_dependencies_uses_grouped_options_and_inline_values() -> None:
    source = (
        "qiime tools export --input-path=in.qza --output-path out-dir "
        "--p-threads 4 --m-metadata-file meta.tsv"
    )
    document = analyze_document(source)

    dependencies = extract_command_dependencies(
        document.commands[0], document.merged_text
    )

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


def test_extract_command_dependencies_trims_inline_quoted_value_span() -> None:
    source = 'qiime demo step --i-table="a.qza" --o-result out.qza'
    document = analyze_document(source)

    dependencies = extract_command_dependencies(
        document.commands[0], document.merged_text
    )

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

    issues = collect_diagnostics(document, dependency_hierarchy)
    cycle_issues = [issue for issue in issues if issue.code == DEPENDENCY_CYCLE]

    assert len(cycle_issues) == 2
    assert {issue.message for issue in cycle_issues} == {
        "Dependency cycle detected for input path 'a.qza'.",
        "Dependency cycle detected for input path 'b.qza'.",
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

    issues = collect_diagnostics(document, dependency_hierarchy)
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

    issues = collect_diagnostics(document, dependency_hierarchy)
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

    issues = collect_diagnostics(document, dependency_hierarchy)

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

    issues = collect_diagnostics(document, dependency_hierarchy)

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

    issues = collect_diagnostics(document, dependency_hierarchy)
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

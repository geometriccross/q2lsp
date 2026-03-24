"""Document-level dependency diagnostics."""

from __future__ import annotations

from collections.abc import Sequence

from q2lsp.lsp.diagnostics import codes
from q2lsp.lsp.diagnostics.diagnostic_issue import DiagnosticIssue
from q2lsp.lsp.diagnostics.models import CommandAnalysis


def collect_document_diagnostics(
    command_analyses: Sequence[CommandAnalysis],
) -> list[DiagnosticIssue]:
    """Collect document-level diagnostics from command dependency edges."""
    producers_by_path: dict[str, list[int]] = {}
    for index, analysis in enumerate(command_analyses):
        for output_ref in analysis.dependencies.outputs:
            producers_by_path.setdefault(output_ref.path, []).append(index)

    adjacency: dict[int, set[int]] = {
        index: set() for index in range(len(command_analyses))
    }
    cyclic_inputs: dict[tuple[int, int, int, str], None] = {}
    edges: list[tuple[int, int, str, int, int]] = []

    for consumer_index, analysis in enumerate(command_analyses):
        for input_ref in analysis.dependencies.inputs:
            for producer_index in producers_by_path.get(input_ref.path, []):
                adjacency[producer_index].add(consumer_index)
                edges.append(
                    (
                        producer_index,
                        consumer_index,
                        input_ref.path,
                        input_ref.start,
                        input_ref.end,
                    )
                )

    node_to_component, components = _get_components(adjacency)
    cyclic_components = {
        component_id
        for component_id, nodes in components.items()
        if len(nodes) > 1 or any(node in adjacency[node] for node in nodes)
    }

    for producer_index, consumer_index, path, start, end in edges:
        producer_component = node_to_component.get(producer_index)
        consumer_component = node_to_component.get(consumer_index)
        if producer_component != consumer_component:
            continue
        if producer_component not in cyclic_components:
            continue
        cyclic_inputs[(consumer_index, start, end, path)] = None

    return [
        DiagnosticIssue(
            message=f"Dependency cycle detected for input path '{path}'.",
            start=start,
            end=end,
            code=codes.DEPENDENCY_CYCLE,
        )
        for (_consumer_index, start, end, path) in cyclic_inputs
    ]


def _get_components(
    adjacency: dict[int, set[int]],
) -> tuple[dict[int, int], dict[int, set[int]]]:
    node_to_component: dict[int, int] = {}
    components: dict[int, set[int]] = {}
    component_index = 0
    reverse_adjacency = _reverse_adjacency(adjacency)

    for node in adjacency:
        if node in node_to_component:
            continue

        reachable = _reachable_nodes(node, adjacency)
        reverse_reachable = _reachable_nodes(node, reverse_adjacency)
        component_nodes = reachable & reverse_reachable

        for component_node in component_nodes:
            node_to_component[component_node] = component_index

        components[component_index] = component_nodes
        component_index += 1

    return node_to_component, components


def _reachable_nodes(start: int, adjacency: dict[int, set[int]]) -> set[int]:
    visited: set[int] = set()
    stack = [start]

    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        stack.extend(adjacency.get(node, ()))

    return visited


def _reverse_adjacency(adjacency: dict[int, set[int]]) -> dict[int, set[int]]:
    reversed_graph: dict[int, set[int]] = {node: set() for node in adjacency}
    for node, neighbors in adjacency.items():
        for neighbor in neighbors:
            reversed_graph.setdefault(neighbor, set()).add(node)
    return reversed_graph

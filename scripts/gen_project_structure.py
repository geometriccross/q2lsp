#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


BEGIN_MARKER = "<!-- BEGIN GENERATED: PROJECT_STRUCTURE -->"
END_MARKER = "<!-- END GENERATED: PROJECT_STRUCTURE -->"

EXCLUDED_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".venv",
    "node_modules",
    ".pixi",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".vscode",
    ".vscode-test",
    "out",
}
EXCLUDED_FILE_NAMES = {".DS_Store"}
EXCLUDED_PATHS = {"src/q2lsp.egg-info"}
EXTRA_DEPTH_PATHS = {"extensions/vscode-q2lsp/src/test"}

ALLOWLIST = [
    (".beads", 1),
    ("extensions", 4),
    ("src", 3),
    ("tests", 2),
    ("pyproject.toml", 0),
]


@dataclass(frozen=True)
class Entry:
    name: str
    path: Path
    is_dir: bool


@dataclass(frozen=True)
class RootEntry:
    entry: Entry
    max_depth: int


def sort_key(name: str) -> tuple[str, str]:
    return (name.casefold(), name)


def should_exclude(path: Path, name: str, is_dir: bool, repo_root: Path) -> bool:
    if is_dir and name in EXCLUDED_DIR_NAMES:
        return True
    if name in EXCLUDED_FILE_NAMES:
        return True
    if name.endswith(".pyc"):
        return True
    try:
        rel = path.relative_to(repo_root).as_posix()
    except ValueError:
        return False
    return rel in EXCLUDED_PATHS


def list_entries(path: Path, repo_root: Path) -> list[Entry]:
    entries: list[Entry] = []
    try:
        with os.scandir(path) as it:
            for dirent in it:
                is_dir = dirent.is_dir(follow_symlinks=False)
                if should_exclude(Path(dirent.path), dirent.name, is_dir, repo_root):
                    continue
                entries.append(Entry(dirent.name, Path(dirent.path), is_dir))
    except OSError as exc:
        raise RuntimeError(f"Failed to read directory: {path}") from exc
    entries.sort(key=lambda entry: sort_key(entry.name))
    return entries


def render_children(
    path: Path,
    repo_root: Path,
    depth: int,
    max_depth: int,
    prefix: str,
) -> list[str]:
    try:
        rel_path = path.relative_to(repo_root).as_posix()
    except ValueError:
        rel_path = ""
    local_max_depth = max_depth + 1 if rel_path in EXTRA_DEPTH_PATHS else max_depth
    if depth >= local_max_depth:
        return []
    lines: list[str] = []
    entries = list_entries(path, repo_root)
    for index, entry in enumerate(entries):
        is_last = index == len(entries) - 1
        connector = "└── " if is_last else "├── "
        name = entry.name + ("/" if entry.is_dir else "")
        lines.append(f"{prefix}{connector}{name}")
        if entry.is_dir:
            child_prefix = prefix + ("    " if is_last else "│   ")
            lines.extend(
                render_children(
                    entry.path,
                    repo_root,
                    depth + 1,
                    max_depth,
                    child_prefix,
                )
            )
    return lines


def build_tree(repo_root: Path) -> list[str]:
    root_entries: list[RootEntry] = []
    for name, max_depth in ALLOWLIST:
        entry_path = repo_root / name
        if not entry_path.exists():
            continue
        is_dir = entry_path.is_dir() and not entry_path.is_symlink()
        root_entries.append(RootEntry(Entry(name, entry_path, is_dir), max_depth))

    lines = ["<Project Root>"]
    for index, root_entry in enumerate(root_entries):
        entry = root_entry.entry
        is_last = index == len(root_entries) - 1
        connector = "└── " if is_last else "├── "
        display_name = entry.name + ("/" if entry.is_dir else "")
        lines.append(f"{connector}{display_name}")
        if entry.is_dir:
            prefix = "    " if is_last else "│   "
            lines.extend(
                render_children(
                    entry.path,
                    repo_root,
                    1,
                    root_entry.max_depth,
                    prefix,
                )
            )
    return lines


def generate_block(repo_root: Path) -> list[str]:
    tree_lines = build_tree(repo_root)
    return ["```", *tree_lines, "```"]


def replace_block(content: str, new_block: Sequence[str]) -> tuple[str, list[str]]:
    lines = content.splitlines()
    begin_indices = [index for index, line in enumerate(lines) if line == BEGIN_MARKER]
    end_indices = [index for index, line in enumerate(lines) if line == END_MARKER]

    if len(begin_indices) != 1:
        raise RuntimeError(
            f"Expected exactly one BEGIN marker in AGENTS.md, found {len(begin_indices)}"
        )
    if len(end_indices) != 1:
        raise RuntimeError(
            f"Expected exactly one END marker in AGENTS.md, found {len(end_indices)}"
        )

    begin_index = begin_indices[0]
    end_index = end_indices[0]

    if begin_index >= end_index:
        raise RuntimeError("Invalid marker order in AGENTS.md")

    existing_block = lines[begin_index + 1 : end_index]
    new_lines = lines[: begin_index + 1] + list(new_block) + lines[end_index:]
    return "\n".join(new_lines) + "\n", existing_block


def diff_blocks(existing: Sequence[str], expected: Sequence[str]) -> str:
    diff = difflib.unified_diff(
        list(existing),
        list(expected),
        fromfile="AGENTS.md",
        tofile="AGENTS.md (expected)",
        lineterm="",
    )
    return "\n".join(diff)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate the project structure section in AGENTS.md.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--check",
        action="store_true",
        help="check whether AGENTS.md is up to date",
    )
    mode_group.add_argument(
        "--write",
        action="store_true",
        help="write updated project structure to AGENTS.md",
    )
    mode_group.add_argument(
        "--stdout",
        action="store_true",
        help="print generated project structure block to stdout",
    )
    args = parser.parse_args()

    try:
        repo_root = Path(__file__).resolve().parents[1]
        new_block = generate_block(repo_root)

        if args.stdout:
            sys.stdout.write("\n".join(new_block) + "\n")
            return 0

        agents_path = repo_root / "AGENTS.md"
        content = agents_path.read_text(encoding="utf-8")
        updated_content, existing_block = replace_block(content, new_block)

        if content == updated_content:
            return 0

        if args.check:
            print(
                "AGENTS.md is out of date. Run: python scripts/gen_project_structure.py"
            )
            print(diff_blocks(existing_block, new_block))
            return 1

        if not args.write and not args.check:
            args.write = True

        agents_path.write_text(updated_content, encoding="utf-8", newline="\n")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path


def resolve_git_dir(repo_root: Path) -> Path:
    dotgit = repo_root / ".git"
    if dotgit.is_dir():
        return dotgit

    if dotgit.is_file():
        content = dotgit.read_text(encoding="utf-8").strip()
        if content.lower().startswith("gitdir:"):
            gitdir = content.split(":", 1)[1].strip()
            return (repo_root / gitdir).resolve()

    raise SystemExit("error: .git directory not found; are you in a git repo?")


def make_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    git_dir = resolve_git_dir(repo_root)

    src = repo_root / ".githooks" / "pre-commit"
    if not src.exists():
        raise SystemExit(f"error: missing hook file: {src}")

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    dest = hooks_dir / "pre-commit"

    shutil.copyfile(src, dest)
    make_executable(dest)

    rel = os.path.relpath(dest, repo_root)
    print(f"installed: {rel}")


if __name__ == "__main__":
    main()

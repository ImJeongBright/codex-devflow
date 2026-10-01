"""Read-only Git evidence and working-tree snapshots."""

import hashlib
import os
from pathlib import Path
import subprocess


def git(repo, *args, check=True):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, timeout=30)
    if check and result.returncode:
        raise ValueError(result.stderr.decode(errors="replace").strip())
    return result


def root(path):
    path = Path(path).expanduser().resolve()
    repo = Path(os.fsdecode(git(path, "rev-parse", "--show-toplevel").stdout).strip()).resolve()
    if not path.samefile(repo):
        raise ValueError(f"Requested repository {path} is not its Git root ({repo}). "
                         "Use the intended Git root or initialize this project as a separate repository.")
    return repo


def files(repo):
    raw = git(repo, "ls-files", "--cached", "--others", "--exclude-standard", "-z").stdout
    return sorted({os.fsdecode(name) for name in raw.split(b"\0") if name
                   and not os.fsdecode(name).startswith(".codex-devflow/")})


def snapshot(repo):
    result = {}
    for name in files(repo):
        path = repo / name
        if path.is_symlink():
            result[name] = "symlink:" + os.readlink(path)
        elif path.is_file():
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            result[name] = f"{path.stat().st_mode & 0o777}:{digest}"
        elif path.is_dir():
            result[name] = "directory/submodule"
    return result


def changed(before, after):
    return sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))


def diff(repo):
    base = git(repo, "rev-parse", "--verify", "HEAD", check=False)
    args = ["diff", "--no-ext-diff", "--no-textconv"]
    if base.returncode == 0:
        args.append("HEAD")
    else:
        args.append("--cached")
    result = git(repo, *args, "--", ".", ":(exclude).codex-devflow").stdout
    if base.returncode:
        result += git(repo, "diff", "--no-ext-diff", "--no-textconv").stdout
    untracked = git(repo, "ls-files", "--others", "--exclude-standard", "-z").stdout
    for raw in untracked.split(b"\0"):
        if not raw:
            continue
        name = os.fsdecode(raw)
        if name.startswith(".codex-devflow/"):
            continue
        result += git(repo, "diff", "--no-index", "--no-ext-diff", "--no-textconv",
                      "--", "/dev/null", name, check=False).stdout
    return result.decode("utf-8", errors="replace")

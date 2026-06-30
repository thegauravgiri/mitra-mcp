import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any

def _run_git_command(args: List[str], cwd: Path) -> str:
    """Helper to run a git command and return stdout or raise an error."""
    if not cwd.exists() or not cwd.is_dir():
        raise ValueError(f"Directory does not exist: {cwd}")
    
    try:
        # Check if git is installed and directory is inside a work tree
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() or e.stdout.strip()
        raise RuntimeError(f"Git command failed: git {' '.join(args)}\nError: {error_msg}")
    except FileNotFoundError:
        raise RuntimeError("Git executable not found on host system.")

def is_git_repo(repo_path: str) -> bool:
    """Checks if the given directory path is inside a git repository."""
    try:
        cwd = Path(repo_path).resolve()
        res = _run_git_command(["rev-parse", "--is-inside-work-tree"], cwd)
        return res.strip() == "true"
    except Exception:
        return False

def get_git_status(repo_path: str) -> str:
    """Gets the output of 'git status --short'."""
    cwd = Path(repo_path).resolve()
    if not is_git_repo(repo_path):
        raise ValueError(f"Not a git repository: {repo_path}")
    return _run_git_command(["status", "--short"], cwd)

def get_git_diff(
    repo_path: str,
    file_path: Optional[str] = None,
    since: Optional[str] = None,
    cached: bool = False
) -> str:
    """
    Gets the git diff.
    - If `since` (commit/branch) is provided, runs 'git diff since HEAD'
    - If `cached` is True, runs 'git diff --cached' (staged changes)
    - If `file_path` is provided, limits diff to that file.
    """
    cwd = Path(repo_path).resolve()
    if not is_git_repo(repo_path):
        raise ValueError(f"Not a git repository: {repo_path}")

    args = ["diff"]
    if cached:
        args.append("--cached")
    elif since:
        args.extend([since, "HEAD"])
    else:
        # Default: show all local changes (staged + unstaged) compared to HEAD
        args.append("HEAD")

    if file_path:
        # Make path relative to repo root if needed, or pass directly
        # git command handles both absolute and relative path, but relative is safer.
        try:
            rel_path = Path(file_path).resolve().relative_to(cwd)
            args.extend(["--", str(rel_path)])
        except ValueError:
            # If file path is not within the repo, just pass it directly
            args.extend(["--", file_path])
    
    return _run_git_command(args, cwd)

def get_recent_commits(repo_path: str, count: int = 5) -> str:
    """Gets the output of 'git log' for the latest N commits."""
    cwd = Path(repo_path).resolve()
    if not is_git_repo(repo_path):
        raise ValueError(f"Not a git repository: {repo_path}")
    
    args = ["log", f"-n", str(count), "--oneline"]
    return _run_git_command(args, cwd)

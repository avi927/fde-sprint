"""Safety layer 2: which MCP tools the agent may call, and with which arguments."""

from dataclasses import dataclass
from enum import Enum


class Access(str, Enum):
    READ = "read"
    WRITE = "write"


class PolicyViolation(Exception):
    """Raised when a tool call is not allowed. The call is never sent to the server."""


@dataclass(frozen=True)
class RepoTarget:
    """The only repository and base branch the agent may touch."""

    owner: str
    repo: str
    base_branch: str


# (server, tool) -> access. Anything not listed is forbidden.
ALLOWED_TOOLS: dict[tuple[str, str], Access] = {
    ("ado", "wit_work_item"): Access.READ,
    ("github", "get_file_contents"): Access.READ,
    ("github", "create_branch"): Access.WRITE,
    ("github", "push_files"): Access.WRITE,
    ("github", "create_pull_request"): Access.WRITE,
}

ADO_READ_ACTIONS = {"get", "list_comments"}
BRANCH_PREFIX = "bugfix/"
WRITABLE_PREFIXES = ("app/",)  # the agent may change application code only - never tests


def is_visible(server: str, tool: str) -> bool:
    """Should the LLM even see this tool?"""
    return (server, tool) in ALLOWED_TOOLS


def check_call(
    server: str, tool: str, arguments: dict, target: RepoTarget, *, writes_approved: bool
) -> Access:
    """Return the access level of an allowed call, or raise PolicyViolation."""
    access = ALLOWED_TOOLS.get((server, tool))
    if access is None:
        raise PolicyViolation(f"{server}.{tool} is not on the allowlist")

    if server == "ado":
        action = arguments.get("action")
        if action not in ADO_READ_ACTIONS:
            raise PolicyViolation(f"Azure DevOps action {action!r} is not allowed")
        return access

    # Every GitHub call must target our repository.
    if arguments.get("owner") != target.owner or arguments.get("repo") != target.repo:
        raise PolicyViolation("GitHub calls must target the configured repository")

    if access is Access.READ:
        return access

    if not writes_approved:
        raise PolicyViolation(f"{tool} needs human approval first")

    if tool == "create_branch":
        _check_branch(arguments.get("branch"))
        if arguments.get("from_branch") != target.base_branch:
            raise PolicyViolation(f"Branches must start from {target.base_branch}")
    elif tool == "push_files":
        _check_branch(arguments.get("branch"))
        files = arguments.get("files") or []
        if not files:
            raise PolicyViolation("push_files needs at least one file")
        for file in files:
            _check_path(str(file.get("path", "")))
    elif tool == "create_pull_request":
        _check_branch(arguments.get("head"))
        if arguments.get("base") != target.base_branch:
            raise PolicyViolation(f"Pull requests must target {target.base_branch}")
        if arguments.get("draft") is not True:
            raise PolicyViolation("Pull requests must be drafts")
    return access


def _check_branch(branch: object) -> None:
    if not isinstance(branch, str) or not branch.startswith(BRANCH_PREFIX):
        raise PolicyViolation(f"Branch must start with {BRANCH_PREFIX!r}")


def _check_path(path: str) -> None:
    if ".." in path.split("/") or path.startswith("/"):
        raise PolicyViolation(f"Unsafe path: {path}")
    if not path.startswith(WRITABLE_PREFIXES):
        raise PolicyViolation(f"The agent may not change {path}")
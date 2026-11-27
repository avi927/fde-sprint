"""Unit tests for app/agent/policy.py - the agent's tool allowlist."""

import pytest

from app.agent.policy import Access, PolicyViolation, RepoTarget, check_call, is_visible

TARGET = RepoTarget(owner="me", repo="proj", base_branch="bug-playground")
REPO = {"owner": "me", "repo": "proj"}


def call(server, tool, arguments, writes_approved=False):
    return check_call(server, tool, arguments, TARGET, writes_approved=writes_approved)


def test_reading_a_bug_is_allowed():
    assert call("ado", "wit_work_item", {"action": "get", "id": 1}) is Access.READ


def test_other_ado_actions_are_blocked():
    with pytest.raises(PolicyViolation):
        call("ado", "wit_work_item", {"action": "my"})


@pytest.mark.parametrize(
    ("server", "tool"),
    [
        ("ado", "wit_work_item_comment_write"),
        ("ado", "wit_work_item_write"),
        ("github", "merge_pull_request"),
        ("github", "get_commit"),
        ("github", "list_commits"),
        ("github", "search_commits"),
    ],
)
def test_forbidden_tools_are_blocked_and_hidden(server, tool):
    assert not is_visible(server, tool)
    with pytest.raises(PolicyViolation):
        call(server, tool, {**REPO, "action": "get"}, writes_approved=True)


def test_reading_a_file_in_our_repo_is_allowed():
    assert call("github", "get_file_contents", {**REPO, "path": "app/rag.py"}) is Access.READ


def test_other_repositories_are_blocked():
    with pytest.raises(PolicyViolation):
        call("github", "get_file_contents", {"owner": "someone", "repo": "else", "path": "x"})


def test_writes_need_approval():
    with pytest.raises(PolicyViolation):
        call("github", "create_branch", {**REPO, "branch": "bugfix/1", "from_branch": "bug-playground"})


def test_approved_branch_from_base_is_allowed():
    arguments = {**REPO, "branch": "bugfix/14098-overlap", "from_branch": "bug-playground"}
    assert call("github", "create_branch", arguments, writes_approved=True) is Access.WRITE


@pytest.mark.parametrize(
    "arguments",
    [
        {**REPO, "branch": "main", "from_branch": "bug-playground"},
        {**REPO, "branch": "bugfix/1", "from_branch": "main"},
    ],
)
def test_bad_branches_are_blocked(arguments):
    with pytest.raises(PolicyViolation):
        call("github", "create_branch", arguments, writes_approved=True)


@pytest.mark.parametrize("path", ["tests/test_chunking.py", ".env", "app/../.env", ".github/workflows/x.yml"])
def test_pushing_outside_app_is_blocked(path):
    arguments = {**REPO, "branch": "bugfix/1", "files": [{"path": path, "content": "x"}]}
    with pytest.raises(PolicyViolation):
        call("github", "push_files", arguments, writes_approved=True)


def test_pushing_app_code_to_bugfix_branch_is_allowed():
    arguments = {**REPO, "branch": "bugfix/1", "files": [{"path": "app/chunking.py", "content": "x"}]}
    assert call("github", "push_files", arguments, writes_approved=True) is Access.WRITE


def test_pull_request_must_be_a_draft_into_base():
    good = {**REPO, "head": "bugfix/1", "base": "bug-playground", "draft": True}
    assert call("github", "create_pull_request", good, writes_approved=True) is Access.WRITE
    for bad in ({**good, "draft": False}, {**good, "base": "main"}, {**good, "head": "feature/x"}):
        with pytest.raises(PolicyViolation):
            call("github", "create_pull_request", bad, writes_approved=True)
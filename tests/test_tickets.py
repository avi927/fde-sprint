"""Unit tests for app/agent/tickets.py (no network, no server)."""

import json

import pytest

from app.agent.tickets import (
    TicketError,
    area_from_title,
    html_to_text,
    parse_bug,
    unwrap_untrusted,
)

MARK = "0123456789abcdef0123456789abcdef"


def wrap(body: str) -> str:
    """Wrap text the way the Azure DevOps MCP server does."""
    return f"<<{MARK}>> [UNTRUSTED AZURE DEVOPS WORK-ITEMS CONTENT] <<{MARK}>>\n{body}\n<</{MARK}>>"


def work_item(work_item_type: str = "Bug", title: str = "BE - Something breaks") -> dict:
    return {
        "id": 101,
        "fields": {
            "System.WorkItemType": work_item_type,
            "System.Title": title,
            "System.State": "New",
            "Microsoft.VSTS.Common.Priority": 2,
            "Microsoft.VSTS.Common.Severity": "3 - Medium",
            "Microsoft.VSTS.TCM.ReproSteps": "<div>1. Do this.<br></div><div>Expected: A &amp; B</div>",
            "System.CommentCount": 0,
        },
    }


def test_html_to_text_real_repro_steps_format():
    html = (
        "<div><span>1. Call POST /ask with an empty question.<br></span>"
        "<div>2. Observe the response.<br> </div>"
        "<div>Expected: 422 validation error.<br> </div>"
        "<span>Actual: Sample bug.</span><br> </div>"
    )
    assert html_to_text(html) == (
        "1. Call POST /ask with an empty question.\n"
        "2. Observe the response.\n"
        "Expected: 422 validation error.\n"
        "Actual: Sample bug."
    )


def test_html_to_text_decodes_entities_and_nbsp():
    assert html_to_text("<p>a&nbsp;&amp;&nbsp;b &lt;tag&gt;</p>") == "a & b <tag>"


def test_unwrap_untrusted_returns_inner_body():
    assert unwrap_untrusted(wrap('{"id": 1}')) == '{"id": 1}'


def test_unwrap_untrusted_without_markers_returns_text():
    assert unwrap_untrusted('  {"id": 1}  ') == '{"id": 1}'


@pytest.mark.parametrize(
    ("title", "expected"),
    [("BE - Search bug", "BE"), ("fe- Button broken", "FE"), ("Search bug", None)],
)
def test_area_from_title(title, expected):
    assert area_from_title(title) == expected


def test_parse_bug_builds_clean_ticket():
    ticket = parse_bug(wrap(json.dumps(work_item())))
    assert ticket.id == 101
    assert ticket.area == "BE"
    assert ticket.priority == 2
    assert ticket.repro_steps == "1. Do this.\nExpected: A & B"


def test_parse_bug_rejects_other_work_item_types():
    with pytest.raises(TicketError):
        parse_bug(wrap(json.dumps(work_item(work_item_type="Task"))))


def test_parse_bug_rejects_invalid_json():
    with pytest.raises(TicketError):
        parse_bug(wrap("not json"))
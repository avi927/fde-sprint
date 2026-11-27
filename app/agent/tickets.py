"""Turn raw Azure DevOps work item responses into a clean, minimal BugTicket."""

import json
import re
from html.parser import HTMLParser
from typing import Literal

from pydantic import BaseModel, ConfigDict

# The fields we ask the server for. Nothing else (no names, emails or identity IDs).
BUG_FIELDS = [
    "System.WorkItemType",
    "System.Title",
    "System.State",
    "Microsoft.VSTS.Common.Priority",
    "Microsoft.VSTS.Common.Severity",
    "Microsoft.VSTS.TCM.ReproSteps",
    "System.CommentCount",
]

# <<marker>> [UNTRUSTED ...] <<marker>> BODY <</marker>>
_UNTRUSTED = re.compile(
    r"<<(?P<tag>[0-9a-fA-F]{16,})>>.*?<<(?P=tag)>>(?P<body>.*)<</(?P=tag)>>",
    re.DOTALL,
)
_AREA_PREFIX = re.compile(r"^\s*(BE|FE)\s*-", re.IGNORECASE)


class TicketError(Exception):
    """Raised when a work item can't be turned into a BugTicket."""


class BugTicket(BaseModel):
    """Only what the agent needs to understand a bug."""

    model_config = ConfigDict(frozen=True)

    id: int
    title: str
    area: Literal["BE", "FE"] | None
    state: str
    priority: int | None
    severity: str | None
    repro_steps: str
    comment_count: int


class _TextExtractor(HTMLParser):
    """Collect visible text; block-level tags become line breaks."""

    _BREAKS = {"br", "div", "p", "li", "ul", "ol", "tr", "h1", "h2", "h3", "h4", "pre"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self._BREAKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._BREAKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(html: str) -> str:
    """Rich-text HTML -> plain text: one line per block, no tags, no empty lines."""
    extractor = _TextExtractor()
    extractor.feed(html)
    extractor.close()
    text = "".join(extractor.parts).replace("\xa0", " ")
    lines = (line.strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def unwrap_untrusted(text: str) -> str:
    """Return the content inside the server's untrusted-content markers (or the text as is)."""
    match = _UNTRUSTED.search(text)
    return match.group("body").strip() if match else text.strip()


def area_from_title(title: str) -> Literal["BE", "FE"] | None:
    """'BE - ...' -> 'BE', 'FE - ...' -> 'FE', anything else -> None."""
    match = _AREA_PREFIX.match(title)
    return match.group(1).upper() if match else None  # type: ignore[return-value]


def parse_bug(raw_text: str) -> BugTicket:
    """Raw wit_work_item text (markers + JSON) -> BugTicket. Raises TicketError."""
    try:
        data = json.loads(unwrap_untrusted(raw_text))
    except json.JSONDecodeError as error:
        raise TicketError(f"Work item response is not valid JSON: {error}") from error

    fields = data.get("fields", {})
    work_item_type = fields.get("System.WorkItemType")
    if work_item_type != "Bug":
        raise TicketError(f"Work item {data.get('id')} is a {work_item_type}, not a Bug")

    title = fields.get("System.Title", "")
    return BugTicket(
        id=data["id"],
        title=title,
        area=area_from_title(title),
        state=fields.get("System.State", ""),
        priority=fields.get("Microsoft.VSTS.Common.Priority"),
        severity=fields.get("Microsoft.VSTS.Common.Severity"),
        repro_steps=html_to_text(fields.get("Microsoft.VSTS.TCM.ReproSteps", "")),
        comment_count=fields.get("System.CommentCount", 0),
    )
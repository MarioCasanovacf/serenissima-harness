"""ATX heading extraction for mdtoc (T-021).

Scans Markdown source line-by-line and yields `Heading` records for ATX
headings (`# Title`), while correctly ignoring:
  - headings that appear inside fenced code blocks (``` or ~~~ fences,
    including an info string like ```python), and
  - headings that appear inside HTML comments (`<!-- ... -->`), even when
    the comment spans multiple lines.

Python 3.9+ stdlib only (re only). No third-party dependencies.
"""
import re
from typing import List, NamedTuple


class Heading(NamedTuple):
    """One ATX heading found in a Markdown document."""

    level: int
    text: str
    line: int


# An ATX heading line: up to 3 leading spaces, 1-6 '#' characters, then AT
# LEAST one space/tab separator, then the rest of the line as heading
# content (which may be empty, e.g. "# "). A 7th '#' or a missing separator
# (e.g. "#nospace") leaves trailing/adjacent characters that this pattern
# cannot consume, so the whole line simply fails to match -- no special
# casing needed for either "not a heading" rule.
_HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*)$")

# A fence-opening (or fence-closing) candidate line: up to 3 leading spaces
# then a run of 3+ backticks or tildes, optionally followed by an info
# string (e.g. "```python"). The run length and character are inspected by
# the caller to decide open vs. close semantics.
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")

_HTML_COMMENT_OPEN = "<!--"
_HTML_COMMENT_CLOSE = "-->"


def _strip_closing_sequence(text: str) -> str:
    """Strip a trailing ATX closing run of '#' (e.g. "Title ##" -> "Title").

    Per the ATX spec, the closing run must be preceded by whitespace (so
    "Title##" is left untouched -- that '#' run is just literal text). A
    heading whose entire content is a run of '#' (e.g. from "# #") has no
    real text, so it collapses to the empty string.
    """
    if not text:
        return text
    if set(text) == {"#"}:
        return ""
    match = re.fullmatch(r"(.*?)[ \t]+#+", text)
    if match:
        return match.group(1)
    return text


def parse_headings(text: str) -> List[Heading]:
    """Return every ATX heading in `text`, in document order.

    Headings inside fenced code blocks or HTML comments are skipped. Line
    numbers are 1-based and refer to the physical line the heading starts on.
    """
    headings: List[Heading] = []

    in_fence = False
    fence_char = ""
    fence_len = 0

    in_comment = False

    for line_no, line in enumerate(text.splitlines(), start=1):
        if in_fence:
            # Only a matching-or-longer run of the SAME fence character,
            # alone on the line (aside from leading indent/trailing
            # whitespace), closes the fence.
            close_re = re.compile(
                r"^ {0,3}" + re.escape(fence_char) + "{" + str(fence_len) + ",}[ \t]*$"
            )
            if close_re.match(line):
                in_fence = False
            continue  # code (or the fence delimiter itself) is never a heading

        fence_match = _FENCE_RE.match(line)
        if fence_match and not in_comment:
            in_fence = True
            fence_char = fence_match.group(1)[0]
            fence_len = len(fence_match.group(1))
            continue

        if in_comment:
            close_at = line.find(_HTML_COMMENT_CLOSE)
            if close_at == -1:
                continue  # whole line still inside the comment
            in_comment = False
            line = line[close_at + len(_HTML_COMMENT_CLOSE):]
            # fall through: re-check whatever trails the closing marker

        open_at = line.find(_HTML_COMMENT_OPEN)
        if open_at != -1:
            close_at = line.find(_HTML_COMMENT_CLOSE, open_at + len(_HTML_COMMENT_OPEN))
            if close_at == -1:
                # Comment opens here and continues on later lines; only the
                # portion before it is live text on this line.
                in_comment = True
                line = line[:open_at]
            else:
                # Opens and closes on the same line: mask the commented
                # span (preserving column positions) and keep scanning.
                span_len = (close_at + len(_HTML_COMMENT_CLOSE)) - open_at
                line = line[:open_at] + (" " * span_len) + line[close_at + len(_HTML_COMMENT_CLOSE):]

        match = _HEADING_RE.match(line)
        if not match:
            continue

        level = len(match.group(1))
        content = _strip_closing_sequence(match.group(2).strip())
        headings.append(Heading(level=level, text=content, line=line_no))

    return headings

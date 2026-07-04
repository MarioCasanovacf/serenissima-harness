"""mdtoc inserter: nested TOC rendering + idempotent marker-based insertion.

This module is intentionally decoupled from the slugger implementation: the
``slugify`` callable is INJECTED by the caller (see ``render_toc``), so this
module never imports the slugger package/module. That keeps ``inserter.py``
on the parallel frontier of the mdtoc DAG -- there is deliberately no import
edge from here to the slugger tournament (T-023..T-027).

Likewise, ``render_toc`` never imports ``mdtoc.parser``: it accepts any
iterable of heading-like objects that duck-type ``.level`` (int) and
``.text`` (str) -- e.g. ``mdtoc.parser.Heading`` namedtuples, plain
``collections.namedtuple`` stand-ins used in tests, or any other object with
those two attributes.

Public API
----------
render_toc(headings, slugify, max_depth=3) -> str
    Build a nested Markdown bullet-list Table of Contents.

insert_toc(text, toc) -> str | None
    Idempotently replace the content strictly between the
    ``<!-- toc -->`` / ``<!-- tocstop -->`` markers with ``toc``.
"""

TOC_START_MARKER = "<!-- toc -->"
TOC_STOP_MARKER = "<!-- tocstop -->"


def render_toc(headings, slugify, max_depth=3):
    """Render a nested Markdown bullet-list Table of Contents.

    Parameters
    ----------
    headings : iterable of heading-like objects
        Each item must expose ``.level`` (int, 1-based) and ``.text`` (str)
        attributes. Duck-typed on purpose -- this function never imports
        ``mdtoc.parser``.
    slugify : callable
        An INJECTED callable with signature
        ``slugify(text: str, seen: dict) -> str``. A single ``seen`` dict is
        created here and shared across the *entire* document (passed to
        every call), so duplicate heading text dedupes consistently
        (e.g. a slugify implementation might yield ``foo``, then
        ``foo-1`` for a second heading also literally titled ``foo``).
        ``render_toc`` does not inspect or rely on ``seen``'s contents; it
        only guarantees the SAME dict instance is threaded through every
        call for a given ``render_toc`` invocation.
    max_depth : int, default 3
        Headings whose ``level`` is strictly greater than ``max_depth`` are
        omitted from the TOC entirely. They are also excluded when
        computing the "shallowest included level" used for indentation, so
        omitted deep headings never affect the indentation of headings that
        ARE included.

    Returns
    -------
    str
        The rendered TOC: one bullet line per included heading of the form
        ``'{indent}- [{text}](#{anchor})'``, newline-joined, with NO
        trailing newline. Returns ``""`` (empty string) if no heading has
        ``level <= max_depth``.

    Indentation
    -----------
    ``indent = '  ' * (heading.level - shallowest_included_level)`` where
    ``shallowest_included_level`` is the minimum ``.level`` among headings
    that passed the ``max_depth`` filter. Two spaces per relative level.
    """
    included = [h for h in headings if h.level <= max_depth]
    if not included:
        return ""

    shallowest = min(h.level for h in included)
    seen = {}
    lines = []
    for h in included:
        anchor = slugify(h.text, seen)
        indent = "  " * (h.level - shallowest)
        lines.append("{indent}- [{text}](#{anchor})".format(
            indent=indent, text=h.text, anchor=anchor
        ))
    return "\n".join(lines)


def insert_toc(text, toc):
    """Idempotently replace the content between the TOC markers.

    Contract
    --------
    - If BOTH ``TOC_START_MARKER`` ('<!-- toc -->') and ``TOC_STOP_MARKER``
      ('<!-- tocstop -->') are present in ``text``, with the stop marker
      occurring at or after the end of the start marker, everything
      STRICTLY BETWEEN them is replaced by ``toc``. The markers themselves,
      and all text before the start marker / after the stop marker, are
      left byte-for-byte untouched. The replacement region is delimited
      purely by the two marker strings, never by any previously-inserted
      TOC content -- which is what makes repeated calls idempotent (see
      below).
    - Markers-absent (or malformed) return contract: if the start marker is
      missing, OR the stop marker is missing, OR no stop marker can be found
      AT OR AFTER the start marker's end, this function makes NO changes and
      returns ``None``. It never fabricates marker lines and never
      partially edits ``text``. Callers (e.g. the mdtoc CLI) are expected to
      check for this ``None`` sentinel and fall back to printing the
      rendered TOC to stdout instead of silently no-op'ing on disk.
    - IDEMPOTENT: ``insert_toc(insert_toc(text, toc), toc)`` is
      byte-for-byte identical to ``insert_toc(text, toc)``. This holds
      because each call re-locates the start/stop markers fresh in its
      input and replaces only the span between them; the second call finds
      the very same two marker strings (now bracketing the ``toc`` inserted
      by the first call) and replaces that span with the identical ``toc``
      argument, reproducing the same output.

    Parameters
    ----------
    text : str
        The full document text to search for markers.
    toc : str
        The rendered TOC body to place between the markers (typically the
        output of ``render_toc``). No trailing/leading newline is assumed
        or required; ``insert_toc`` supplies the newlines that separate the
        markers from ``toc``.

    Returns
    -------
    str or None
        The updated document text, or ``None`` if the markers are not both
        present (see contract above).
    """
    start_idx = text.find(TOC_START_MARKER)
    if start_idx == -1:
        return None

    after_start = start_idx + len(TOC_START_MARKER)
    stop_idx = text.find(TOC_STOP_MARKER, after_start)
    if stop_idx == -1:
        return None

    before = text[:after_start]
    after = text[stop_idx:]
    return "{before}\n{toc}\n{after}".format(before=before, toc=toc, after=after)

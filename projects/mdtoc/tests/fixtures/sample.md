# Sample Document

<!-- toc -->
<!-- tocstop -->

Welcome to the mdtoc sample fixture. It exercises code fences, HTML
comments, duplicate headings, and unicode headings all in one file.

## Introduction

Here is a fenced code block containing a line that looks like a heading but
must NOT be picked up by the parser or appear in the TOC:

```python
# This looks like a heading but it's inside a fenced code block.
def foo():
    pass
```

Here is a multi-line HTML comment containing another fake heading, which
must also be ignored:

<!--
This HTML comment contains a line that looks like a heading:
# Not A Real Heading
-->

## Café

Some café-related content. This heading is intentionally duplicated below
to exercise anchor dedupe.

## Café

A duplicate of the heading above (same text) -- the second occurrence must
get the deduped anchor `#café-1`.

## 你好世界

A CJK (Chinese) heading meaning "Hello World", to exercise non-Latin
unicode slugging.

### Nested Section

A level-3 heading, included in the TOC at the default `--max-depth 3`.

#### Too Deep

A level-4 heading, excluded from the TOC at the default `--max-depth 3`
(and also excluded at `--max-depth 2`, which additionally excludes the
level-3 "Nested Section" heading above).

## Conclusion

The end of the sample document.

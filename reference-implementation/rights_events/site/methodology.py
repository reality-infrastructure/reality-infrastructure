"""Methodology page renderer (Contract 4).

Renders METHODOLOGY.md — the canonical source at the repository
root — into the site's methodology page. Stdlib line-based rendering
for exactly the constructs the note uses: one # title, ## sections,
paragraphs, "- " list items, [text](https-url) links, and `code`
spans. The note's formatting is constrained to fit this renderer, not
the other way around (Contract 4 plan gate). A drift test re-renders
the canonical source and byte-compares against the committed page.
"""

from __future__ import annotations

import re

from rights_events.site.html import esc, page

ONE_LINER = (
    "Evidence typing, contradiction preservation, and byte-identical "
    "replay — the method behind the four views, with its limits "
    "stated plainly.")

_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _inline(text: str) -> str:
    """Inline rendering: code spans, https links, everything escaped."""
    out: list[str] = []
    for part in re.split(r"(`[^`]*`)", text):
        if len(part) >= 2 and part.startswith("`") and part.endswith("`"):
            out.append(f"<code>{esc(part[1:-1])}</code>")
            continue
        pos = 0
        for m in _LINK_RE.finditer(part):
            out.append(esc(part[pos:m.start()]))
            label, url = m.group(1), m.group(2)
            if url.startswith("https://"):
                out.append(f'<a href="{esc(url)}" rel="noopener">'
                           f"{esc(label)}</a>")
            else:
                out.append(esc(m.group(0)))
            pos = m.end()
        out.append(esc(part[pos:]))
    return "".join(out)


def render_methodology(md_text: str) -> str:
    """METHODOLOGY.md -> full methodology page HTML."""
    title = "Methodology"
    blocks: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(f"  <p>{_inline(' '.join(paragraph))}</p>\n")
            paragraph.clear()

    def flush_list() -> None:
        if list_items:
            items = "".join(f"    <li>{item}</li>\n"
                            for item in list_items)
            blocks.append(f"  <ul>\n{items}  </ul>\n")
            list_items.clear()

    for raw_line in md_text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            flush_paragraph()
            flush_list()
        elif line.startswith("## "):
            flush_paragraph()
            flush_list()
            blocks.append(f"  <h2>{_inline(line[3:])}</h2>\n")
        elif line.startswith("# "):
            flush_paragraph()
            flush_list()
            title = line[2:].strip()
        elif line.startswith("- "):
            flush_paragraph()
            list_items.append(_inline(line[2:]))
        else:
            flush_list()
            paragraph.append(line.strip())
    flush_paragraph()
    flush_list()

    return page(title, "".join(blocks), "../style.css",
                crumbs='<a href="../index.html">Index</a> / Methodology')

"""Shared HTML assembly: escaping, page chrome, limits language.

Escaping rules (plan-gate item 4): every interpolated value passes
esc() (html.escape with quote=True) — record strings land only in text
nodes and quoted attributes; source URLs become links only when their
scheme is exactly https, otherwise they render as escaped text; no
markup is ever built from record data.

LIMITS holds the What-it-does-not-do sentences carried VERBATIM from
the repository README (Contract 3 Constraint 2); a test asserts each
sentence still appears in README.md so the site cannot drift from the
repo's own limits language.
"""

from __future__ import annotations

import html as _html
from urllib.parse import urlsplit

# Verbatim from README.md, "What it does not do". Rendered as an
# explicit quotation from the README (the fourth sentence's
# self-reference reads correctly in quotation).
LIMITS: tuple[str, ...] = (
    "It proves what was claimed, not what is true. Garbage claims, "
    "faithfully logged, are still garbage — they are simply garbage "
    "with provenance, which is what makes them auditable.",
    "It is not a detector. It cannot determine whether a work was used "
    "to train a model, whether a signature's holder is honest, or "
    "whether a filed deed is forged. It fuses and preserves evidence "
    "produced by other instruments; it does not generate that evidence.",
    "Fusion does not launder weak evidence into strong evidence. The "
    "typed uncertainty is carried through to the output, not hidden "
    "by it.",
    "Evidentiary weight in any legal proceeding is a question for "
    "counsel and courts, not for this README.",
)

REPO_URL = "https://github.com/reality-infrastructure/reality-infrastructure"


def esc(value) -> str:
    """Escape a value for text nodes and quoted attributes."""
    return _html.escape(str(value), quote=True)


def link_https(url: str) -> str:
    """Render a URL as a link only if its scheme is exactly https."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return esc(url)
    if parts.scheme != "https" or not parts.netloc:
        return esc(url)
    return f'<a href="{esc(url)}" rel="noopener">{esc(url)}</a>'


def limits_block() -> str:
    """The README limits, rendered as an explicit quotation."""
    items = "\n".join(f"      <li>{esc(s)}</li>" for s in LIMITS)
    return (
        '  <section class="limits">\n'
        "    <h2>What verification does not prove</h2>\n"
        "    <p>From the repository README, "
        "<cite>What it does not do</cite>:</p>\n"
        "    <ul>\n" + items + "\n    </ul>\n"
        "  </section>\n"
    )


def page(title: str, body: str, css_href: str, crumbs: str = "") -> str:
    """Full page chrome. No dates, no scripts, no external assets."""
    nav = (f'    <nav aria-label="Breadcrumb">{crumbs}</nav>\n'
           if crumbs else "")
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, '
        'initial-scale=1">\n'
        f"  <title>{esc(title)}</title>\n"
        f'  <link rel="stylesheet" href="{esc(css_href)}">\n'
        "</head>\n"
        "<body>\n"
        "  <header>\n"
        f"{nav}"
        f"    <h1>{esc(title)}</h1>\n"
        "  </header>\n"
        "  <main>\n"
        f"{body}"
        "  </main>\n"
        "  <footer>\n"
        "    <p>Generated deterministically from the run artifacts; "
        "the Merkle roots on the evidence page identify this build. "
        f'Source: <a href="{REPO_URL}" rel="noopener">the repository'
        "</a>.</p>\n"
        "  </footer>\n"
        "</body>\n"
        "</html>\n"
    )

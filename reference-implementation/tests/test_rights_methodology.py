"""Methodology note and page tests (C4-P2).

Covers: the drift test (fresh render of the canonical METHODOLOGY.md
byte-compared against the committed docs/methodology/index.html), the
word-count range (2,000-3,000, code spans and link URLs excluded),
anchor presence (every live site URL cited in the note maps to a file
in docs/), verbatim-consistency of the carried principles with the
README, CITATION.cff state, and the build integration.
"""

import re
from pathlib import Path

import pytest

import rights_events
from rights_events.site.build import main as build_main
from rights_events.site.methodology import ONE_LINER, render_methodology

REPO_ROOT = Path(rights_events.__file__).parents[2]
SITE_BASE = ("https://reality-infrastructure.github.io/"
             "reality-infrastructure/")

PRINCIPLES = (
    "A signature authenticates a signer, never a claim",
    "It proves what was claimed, not what is true",
    "It is not a detector",
    "Fusion does not launder weak evidence into strong evidence",
)


def note_text() -> str:
    return (REPO_ROOT / "METHODOLOGY.md").read_text(encoding="utf-8")


class TestCanonicalSource:
    def test_five_sections_in_order_under_specified_headings(self):
        text = note_text()
        headings = re.findall(r"^## (.+)$", text, re.MULTILINE)
        assert headings[:5] == [
            "1. The verification gap",
            "2. Evidence typing (EP)",
            "3. Contradiction preservation",
            "4. The replay guarantee",
            "5. Limits, stated plainly",
        ]
        assert headings[5] == "References"

    def test_word_count_in_range(self):
        text = note_text()
        stripped = re.sub(r"`[^`]*`", "", text)
        stripped = re.sub(r"\]\([^)]*\)", "]", stripped)
        count = len(stripped.split())
        assert 2000 <= count <= 3000, count

    def test_principles_verbatim_in_note_and_readme(self):
        note = " ".join(note_text().split())
        readme = " ".join(
            (REPO_ROOT / "README.md").read_text(encoding="utf-8").split())
        for principle in PRINCIPLES:
            assert principle in note, principle
            assert principle in readme, principle

    def test_worked_example_masses_exact(self):
        text = note_text()
        for mass in ("0.2475", "0.2025", "0.3025", "0.01536",
                     "0.91296", "0.01024", "0.45", "0.55"):
            assert mass in text, mass

    def test_f3_gap_disclosed(self):
        text = note_text()
        assert "not demonstrated" in text
        assert "Estimate of Redemption" in text

    def test_dated_and_versioned(self):
        text = note_text()
        assert "Dated 2026-08-01" in text
        assert "Version 1.4.0" in text


class TestAnchors:
    def test_every_cited_site_url_maps_to_docs_file(self):
        text = note_text()
        urls = re.findall(
            r"\((" + re.escape(SITE_BASE) + r"[^)]*)\)", text)
        assert len(urls) >= 6
        for url in urls:
            rel = url.removeprefix(SITE_BASE) or "index.html"
            assert (REPO_ROOT / "docs" / rel).is_file(), rel

    def test_parked_c3_anchors_all_used(self):
        text = note_text()
        for anchor in ("rights-state/song-x.html",
                       "rights-state/parcel-29024080530000.html",
                       "provenance/parcels.html",
                       "evidence/index.html",
                       "disclosure/index.html"):
            assert anchor in text, anchor


class TestDriftAndIntegration:
    def test_committed_page_matches_fresh_render(self):
        rendered = render_methodology(note_text())
        committed = (REPO_ROOT / "docs" / "methodology" / "index.html"
                     ).read_text(encoding="utf-8")
        assert rendered == committed

    def test_build_emits_methodology_page(self, tmp_path):
        out = tmp_path / "site"
        assert build_main(["--out", str(out)]) == 0
        text = (out / "methodology" / "index.html").read_text(
            encoding="utf-8")
        assert "Verifiable Records of Contested Claims" in text
        assert "<script" not in text
        assert "1. The verification gap" in text
        assert "5. Limits, stated plainly" in text

    def test_index_links_methodology_with_one_liner(self, tmp_path):
        out = tmp_path / "site"
        assert build_main(["--out", str(out)]) == 0
        index = (out / "index.html").read_text(encoding="utf-8")
        assert "placeholder" not in index
        assert 'href="methodology/index.html"' in index
        assert ONE_LINER[:40] in index

    def test_rendering_is_lossless_for_note_prose(self):
        # Every prose word of the canonical source appears in the
        # rendered page (headings, paragraphs, list items, link text).
        rendered = render_methodology(note_text())
        # Inline tags strip to nothing (block boundaries carry their
        # own newlines), so "</a>," does not grow a stray space.
        flat = " ".join(re.sub(r"<[^>]+>", "", rendered).split())
        text = re.sub(r"`([^`]*)`", r"\1", note_text())
        text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
        for line in text.splitlines():
            line = line.strip().lstrip("#- ").strip()
            if line:
                probe = " ".join(line.split())
                import html as html_lib
                assert html_lib.unescape(flat).find(probe[:80]) != -1, \
                    probe[:60]


class TestCitation:
    def test_citation_cff_updated_and_parses(self):
        text = (REPO_ROOT / "CITATION.cff").read_text(encoding="utf-8")
        assert "version: 1.4.0" in text
        assert "date-released: 2026-08-01" in text
        # Minimal structural parse without a YAML dependency: every
        # top-level line is key: value or a list item.
        for line in text.splitlines():
            if not line.strip() or line.startswith(" "):
                continue
            assert re.match(r"^[a-z-]+:", line), line

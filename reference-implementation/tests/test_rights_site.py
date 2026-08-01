"""Site generator tests (C3-P1 scaffolding scope).

Covers: the one documented build command, double-build byte-identity
(acceptance, Constraint 4), checksum correctness, artifact equality
with the frozen runners' own output, the README-drift test on the
limits language (Constraint 2), and the accessibility/self-containment
floor for the emitted pages.
"""

import hashlib
import re
from pathlib import Path

import pytest

import rights_events
from rights_events.site.build import main as build_main
from rights_events.site.html import LIMITS
from rights_events.song_x import main as song_x_main

REPO_ROOT = Path(rights_events.__file__).parents[2]


def build_site(tmp_path, name="site"):
    out = tmp_path / name
    assert build_main(["--out", str(out)]) == 0
    return out


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)).replace("\\", "/"): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()}


class TestBuild:
    def test_build_emits_expected_files(self, tmp_path):
        out = build_site(tmp_path)
        for rel in ("index.html", "style.css", "evidence/index.html",
                    "evidence/song_x_run.ri", "evidence/parcels_run.ri",
                    "evidence/SHA256SUMS.txt"):
            assert (out / rel).is_file(), rel

    def test_double_build_byte_identical(self, tmp_path):
        first = tree_bytes(build_site(tmp_path, "a"))
        second = tree_bytes(build_site(tmp_path, "b"))
        assert first.keys() == second.keys()
        for rel in first:
            assert first[rel] == second[rel], rel

    def test_checksums_match_files(self, tmp_path):
        out = build_site(tmp_path)
        text = (out / "evidence/SHA256SUMS.txt").read_text(
            encoding="utf-8")
        lines = [ln for ln in text.splitlines() if ln]
        assert lines == sorted(lines, key=lambda ln: ln.split("  ")[1])
        for line in lines:
            digest, name = line.split("  ")
            actual = hashlib.sha256(
                (out / "evidence" / name).read_bytes()).hexdigest()
            assert digest == actual

    def test_artifacts_equal_frozen_runner_output(self, tmp_path):
        out = build_site(tmp_path)
        direct = tmp_path / "direct_song_x.ri"
        assert song_x_main(["--out", str(direct)]) == 0
        assert direct.read_bytes() == \
            (out / "evidence/song_x_run.ri").read_bytes()


class TestLimitsLanguage:
    def test_limits_are_verbatim_from_readme(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        section = readme.split("## What it does not do")[1] \
                        .split("## Status")[0]
        flat = " ".join(section.split())
        for sentence in LIMITS:
            assert " ".join(sentence.split()) in flat, sentence[:50]

    def test_limits_rendered_on_index_and_evidence(self, tmp_path):
        out = build_site(tmp_path)
        for rel in ("index.html", "evidence/index.html"):
            html_text = (out / rel).read_text(encoding="utf-8")
            assert "What verification does not prove" in html_text
            assert "not a detector" in html_text


class TestPageFloor:
    def test_semantic_and_self_contained(self, tmp_path):
        out = build_site(tmp_path)
        for rel in ("index.html", "evidence/index.html"):
            text = (out / rel).read_text(encoding="utf-8")
            assert text.startswith("<!DOCTYPE html>")
            assert '<html lang="en">' in text
            assert "<script" not in text
            assert "http://" not in text  # https links only
            # No external assets: every http(s) reference is a plain
            # anchor, never a stylesheet/font/img src.
            assert not re.search(
                r'(src|href)="https?://[^"]*\.(css|woff2?|js)', text)

    def test_no_timestamps_in_output(self, tmp_path):
        out = build_site(tmp_path)
        for rel in ("index.html", "evidence/index.html", "style.css"):
            text = (out / rel).read_text(encoding="utf-8")
            assert "2026-08" not in text  # no build-date leakage

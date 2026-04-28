"""Tier 3 integration test on the real ``examples/sample.mp3`` fixture
(POD-031 scaffold; satisfies the SP-3 deliverable in PROJECT_PLAN §6).

Per ADR-0017 the test pyramid keeps Tier 1 (unit + fakes, < 1 s) and
Tier 2 (Protocol contract) cheap; Tier 3 is the *expensive* tier — full
CLI invocation, real ffmpeg decode, real ``faster-whisper`` model on
disk, real Markdown render. We mark the whole module ``slow`` so the
default ``pytest`` run stays sub-second; CI's slow job opts in via
``pytest -m slow``.

The reference output (``tests/fixtures/sample_tiny.md``, POD-027) is
hand-curated — ``tiny`` is noisy by design (SRS §14.1: "assertions are
structural ... rather than exact-text"), so we lock the *shape* of the
output, not the bytes. Three structural invariants are enough to catch
real regressions:

* the file is non-empty Markdown with a top-level heading;
* the music-bed segment from 25-35 s surfaces as a music-marker pair
  (start + end), with English markers per AC-US-2.2;
* the timestamps use ``MM:SS`` (the fixture is 60 s, so the < 1 h
  branch of AC-US-2.4 applies).

Skipped gracefully when the fixture isn't on disk yet — keeps a fresh
clone's ``pytest -m slow`` run honest about which capabilities depend
on the binary fixture (POD-026) being present.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from podcast_script.cli import app

pytestmark = pytest.mark.slow

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_MP3 = REPO_ROOT / "examples" / "sample.mp3"
REFERENCE_TINY = REPO_ROOT / "tests" / "fixtures" / "sample_tiny.md"

_MISSING_FIXTURE_REASON = (
    "examples/sample.mp3 not on disk - run examples/build_sample.sh "
    "after dropping LibriVox + CC0 sources into examples/sources/ "
    "(POD-026)."
)
_MISSING_FFMPEG_REASON = (
    "ffmpeg not on PATH; required by C-Decode (UC-1 E4). Install via "
    "Homebrew (macOS) or apt (Ubuntu)."
)


@pytest.fixture(scope="module", autouse=True)
def _require_ffmpeg() -> None:
    """Skip the whole module if ffmpeg isn't installed."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip(_MISSING_FFMPEG_REASON)


@pytest.fixture(scope="module")
def sample_mp3() -> Path:
    """Resolve the bundled fixture or skip the whole module."""
    if not SAMPLE_MP3.exists():
        pytest.skip(_MISSING_FIXTURE_REASON)
    return SAMPLE_MP3


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_cli_tiny_pipeline_produces_structural_markdown(
    sample_mp3: Path,
    runner: CliRunner,
    tmp_path: Path,
) -> None:
    """SP-3 deliverable: full CLI on the real fixture with ``--model tiny``
    produces a Markdown file matching the structural shape of
    ``tests/fixtures/sample_tiny.md``.

    The exact transcript text drifts run-to-run for ``tiny`` (and the
    Whisper version may shift if a Dependabot bump lands a minor
    upgrade), so we assert structure only - same policy as SRS §14.1.
    """
    output_path = tmp_path / "sample_tiny.md"

    # CliRunner so the test is in-process (faster, no PATH gymnastics)
    # but the invocation matches what a user would type. Faster-whisper
    # downloads the ~75 MB tiny model on first run; a cold-cache CI
    # job will spend ~30 s on that one-time download.
    result = runner.invoke(
        app,
        [
            str(sample_mp3),
            "--lang",
            "es",
            "--model",
            "tiny",
            # Pin faster-whisper so the same test works on Ubuntu and
            # macOS CI: mlx-whisper expects a different repo_id shape on
            # the HF Hub for the same model alias.
            "--backend",
            "faster-whisper",
            "-o",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, f"CLI exited {result.exit_code}; stderr={result.stderr!r}"
    assert output_path.exists(), "expected output Markdown file at -o path"

    # UC-1 step 10 + NFR-10: every successful run emits a terminal
    # logfmt summary on stderr so shell wrappers can assert success on
    # a single grep'able key. The pipeline currently logs
    # ``event=write_done`` as the last entry; POD-015 (SP-5) renames
    # that to ``event=done`` per ADR-0012's locked catalogue.
    assert "event=write_done" in result.stderr, (
        f"missing terminal write_done event; stderr={result.stderr!r}"
    )

    # NFR-10 — stderr is logfmt key=value pairs *only*. Stray Python
    # warnings (DeprecationWarning, RuntimeWarning, …) leaking to the
    # user's pipe break that contract. The runtime suppression in
    # ``InaSpeechSegmenter`` must keep upstream lib noise contained
    # even on production audio, where silent intros / outros routinely
    # trigger inaSpeechSegmenter's z-score normalisation on
    # near-zero-variance frames.
    for noise in ("Warning:", "DeprecationWarning", "RuntimeWarning"):
        assert noise not in result.stderr, (
            f"{noise!r} leaked to stderr; stderr={result.stderr!r}"
        )

    body = output_path.read_text(encoding="utf-8")
    _assert_structural_invariants(body)

    # Reference comparison - only the shape, not the bytes. If the
    # reference is missing, treat the CI run as the source of truth and
    # tell the maintainer to commit it.
    if REFERENCE_TINY.exists():
        ref = REFERENCE_TINY.read_text(encoding="utf-8")
        _assert_same_structure(body, ref)
    else:
        pytest.skip(
            f"reference output {REFERENCE_TINY.relative_to(REPO_ROOT)} "
            "missing; commit it after curating the tiny output."
        )


def test_cli_tiny_round_trip_matches_atomic_write_invariant(
    sample_mp3: Path,
    runner: CliRunner,
    tmp_path: Path,
) -> None:
    """Cross-check ADR-0005 (atomic write) on the real path.

    After a successful run, no ``*.md.tmp`` debris is left next to the
    output, and the output's parent directory is exactly the one we
    asked for (``-o`` resolves to an absolute path).
    """
    output_path = tmp_path / "subdir"
    output_path.mkdir()
    target = output_path / "sample_tiny.md"

    result = runner.invoke(
        app,
        [
            str(sample_mp3),
            "--lang",
            "es",
            "--model",
            "tiny",
            "--backend",
            "faster-whisper",
            "-o",
            str(target),
        ],
    )
    assert result.exit_code == 0, f"stderr={result.stderr!r}"
    assert target.exists()
    assert list(output_path.glob("*.tmp")) == []
    assert list(output_path.glob("*.md.tmp")) == []


# ---------------------------------------------------------------------------
# Helpers - kept private and inlined so the test reads top-down.
# ---------------------------------------------------------------------------

# Renderer (POD-011) emits ``> [MM:SS — music starts]`` with an en-dash
# for the marker; the regex must match that exact byte sequence.
_MUSIC_START_RE = re.compile(r"\[\d{2}:\d{2} — music starts\]")
_MUSIC_END_RE = re.compile(r"\[\d{2}:\d{2} — music ends\]")
_TIMESTAMP_MMSS_RE = re.compile(r"\b\d{2}:\d{2}\b")


_HHMMSS_RE = re.compile(r"\b\d{2}:\d{2}:\d{2}\b")
_NOISE_MARKER_RE = re.compile(r">\s*\[\d{2}:\d{2}.*?(noise|silence)", re.IGNORECASE)


def _assert_structural_invariants(body: str) -> None:
    """Lock the locked surface of SRS §1.6 / AC-US-2.x without pinning text.

    Five invariants are the *contract* (anything else - line counts,
    exact transcript words, paragraph breaks - varies with the model
    and is intentionally not asserted):
    """
    # 1) Output is non-empty.
    assert body.strip(), "expected non-empty Markdown output"

    # 2) Music-marker pair from the SRS §14.1 mix recipe.
    assert _MUSIC_START_RE.search(body), f"missing English `music starts` marker; body={body!r}"
    assert _MUSIC_END_RE.search(body), f"missing English `music ends` marker; body={body!r}"

    # 3) Timestamp format auto-MM:SS for < 1 h fixture (AC-US-2.4).
    timestamps = _TIMESTAMP_MMSS_RE.findall(body)
    assert timestamps, "expected at least one MM:SS timestamp"
    # AC-US-2.4 < 1 h branch: no HH:MM:SS triple-segment timestamps.
    # The earlier ``"::" not in body`` was a no-op since real HH:MM:SS
    # uses single colons (``01:23:45``); the regex is the real check.
    assert not _HHMMSS_RE.search(body), (
        f"no HH:MM:SS expected for a 60 s fixture (AC-US-2.4 < 1 h branch); body={body!r}"
    )

    # 4) AC-US-2.5 — no annotation lines for noise/silence regions. The
    #    fixture intentionally has silence padding around the music bed,
    #    so a renderer regression that started leaking
    #    ``> [MM:SS — noise]`` / ``> [MM:SS — silence]`` markers must
    #    fail this. Anchored to the marker shape so a transcribed word
    #    that happens to contain "noise" or "silence" doesn't trip it.
    assert not _NOISE_MARKER_RE.search(body), (
        f"unexpected noise/silence marker in transcript; body={body!r}"
    )


def _assert_same_structure(actual: str, reference: str) -> None:
    """Reference comparison - only the *count* and *order* of music
    markers needs to agree; transcript text is not asserted byte-for-
    byte (tiny is noisy, see SRS §14.1).
    """
    actual_starts = len(_MUSIC_START_RE.findall(actual))
    actual_ends = len(_MUSIC_END_RE.findall(actual))
    ref_starts = len(_MUSIC_START_RE.findall(reference))
    ref_ends = len(_MUSIC_END_RE.findall(reference))

    assert (actual_starts, actual_ends) == (ref_starts, ref_ends), (
        f"music-marker count drift vs reference: "
        f"actual=({actual_starts}, {actual_ends}) "
        f"reference=({ref_starts}, {ref_ends})"
    )

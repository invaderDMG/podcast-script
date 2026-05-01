"""Tier 3 integration test for EC-3 — input/output paths with whitespace
and non-ASCII characters MUST round-trip through the full CLI (POD-028,
SP-7 deliverable in PROJECT_PLAN §6).

EC-3 (SRS §7) is the documented edge case "user passes
``./canción de prueba.mp3`` (whitespace + non-ASCII characters)". The
load-bearing implementation choice is :func:`subprocess.run` invoked
with a list of arguments rather than a shell string, locked in
``decode.py`` (POD-007 / R-4 / SYSTEM_DESIGN §5.6). Tier 1 coverage
already exists at ``tests/test_decode.py::test_decode_handles_path_with_
spaces_and_non_ascii_EC_3`` and ``tests/test_cli.py::test_quoted_value_
with_special_chars_round_trips``; this module adds the missing **Tier 3
end-to-end** layer per ADR-0017 — real ffmpeg decode, real
``faster-whisper`` tiny transcribe, real Markdown render, real atomic
write — on the EC-3 path.

The fixture is materialised at test runtime by copying the bundled
``examples/sample.mp3`` (POD-026) into a directory whose **name carries
whitespace + non-ASCII** and whose **leaf filename carries whitespace +
non-ASCII**. The output ``-o`` path receives the same EC-3 treatment so
the atomic-write tempfile + ``os.replace`` pair (ADR-0005) is exercised
on a non-ASCII parent directory too.

Skipped gracefully when the bundled fixture isn't on disk yet — same
policy as ``test_integration_tiny.py`` (POD-031).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from podcast_script.cli import app

pytestmark = pytest.mark.slow

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_MP3 = REPO_ROOT / "examples" / "sample.mp3"

_EC3_INPUT_DIR_NAME = "carpeta con espacios"
_EC3_INPUT_FILE_NAME = "canción de prueba.mp3"
_EC3_OUTPUT_DIR_NAME = "salida con tildes"
_EC3_OUTPUT_FILE_NAME = "canción de prueba.md"

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


@pytest.fixture
def ec3_input(sample_mp3: Path, tmp_path: Path) -> Path:
    """Materialise an EC-3 input path under ``tmp_path``.

    Both the parent directory **and** the leaf filename carry whitespace
    + non-ASCII so the test exercises the full POSIX argv-quoting
    surface, not just one half. Copying the bundled fixture keeps the
    test deterministic (same audio bytes as Tier 3 baseline) without
    duplicating ~1.5 MB of binary in ``tests/fixtures/``.
    """
    parent = tmp_path / _EC3_INPUT_DIR_NAME
    parent.mkdir()
    target = parent / _EC3_INPUT_FILE_NAME
    shutil.copy(sample_mp3, target)
    return target


def test_cli_round_trips_ec_3_path_with_spaces_and_non_ascii(
    ec3_input: Path,
    runner: CliRunner,
    tmp_path: Path,
) -> None:
    """EC-3 — full CLI round-trips when the input path **and** the output
    path both carry whitespace + non-ASCII characters.

    Pins R-4 (SYSTEM_DESIGN Risk #6) at the integration boundary: the
    list-arg ``subprocess.run`` form in C-Decode (POD-007) is the only
    safe way to forward such paths to ``ffmpeg`` on POSIX, and a future
    refactor to ``shell=True`` or string concatenation would silently
    break this test before reaching production.
    """
    output_dir = tmp_path / _EC3_OUTPUT_DIR_NAME
    output_dir.mkdir()
    output_path = output_dir / _EC3_OUTPUT_FILE_NAME

    result = runner.invoke(
        app,
        [
            str(ec3_input),
            "--lang",
            "es",
            "--model",
            "tiny",
            # Pin faster-whisper so the test runs identically on Ubuntu
            # and macOS CI; mlx-whisper expects a different repo_id
            # shape on the HF Hub for the same model alias.
            "--backend",
            "faster-whisper",
            "-o",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, f"CLI exited {result.exit_code}; stderr={result.stderr!r}"
    assert output_path.exists(), f"expected EC-3 output Markdown at {output_path!s}"

    # NFR-10 / ADR-0012 — the locked terminal summary fires on success.
    assert "event=done" in result.stderr, f"missing terminal done event; stderr={result.stderr!r}"

    # NFR-10 — the EC-3 input path must surface inside ``event=done`` as
    # a *quoted* ``input="…"`` token (whitespace forces logfmt
    # quoting). This is the contract downstream shell wrappers grep
    # for, so the byte sequence has to survive the full pipeline.
    done_line = next(line for line in result.stderr.splitlines() if "event=done" in line)
    assert f'input="{ec3_input!s}"' in done_line, (
        f"expected EC-3 path verbatim in done line; got {done_line!r}"
    )

    # NFR-10 — stderr is logfmt key=value pairs only. Stray Python
    # warnings from upstream libs (faster-whisper, ctranslate2,
    # inaSpeechSegmenter) leaking on the EC-3 path would break the
    # contract just as readily as on the ASCII path; the runtime
    # suppression policy (PR #18, segment.py + backends/base.py) does
    # not depend on the input filename, so any drift here is a real
    # regression.
    for noise in ("Warning:", "DeprecationWarning", "RuntimeWarning"):
        assert noise not in result.stderr, f"{noise!r} leaked to stderr; stderr={result.stderr!r}"

    # POD-033 — every podcast_script-emitted log line on stderr matches
    # the locked logfmt grammar. The quoted-value branch of the regex
    # is the one EC-3 hits (whitespace forces quoting), so a regex
    # narrowing that accidentally rejected non-ASCII inside quotes
    # would fail this check.
    _assert_all_log_lines_match_logfmt(result.stderr)

    # ADR-0005 — atomic write leaves no ``.tmp`` debris in the output
    # directory on success. The EC-3 parent dir name must not perturb
    # ``tempfile.NamedTemporaryFile(dir=output.parent)``.
    assert list(output_dir.glob("*.tmp")) == []
    assert list(output_dir.glob("*.md.tmp")) == []

    # Output must be non-empty Markdown — sanity-check that the bytes
    # we wrote are actually the rendered transcript, not an empty file
    # produced by a degraded pipeline.
    body = output_path.read_text(encoding="utf-8")
    assert body.strip(), f"expected non-empty Markdown at {output_path!s}"


# ---------------------------------------------------------------------------
# Helpers - kept private and inlined per the codebase's "each test module
# reads top-down" convention (cf. test_integration_tiny.py).
# ---------------------------------------------------------------------------

# POD-033 — same logfmt grammar as locked in
# ``tests/test_cli.py::TestNFR10LogfmtRegex._PAIR``.
_LOGFMT_PAIR = r'[A-Za-z_][A-Za-z0-9_]*=(?:"(?:[^"\\]|\\.)*"|[^\s="]+)'
_LOGFMT_LINE_RE = re.compile(rf"^{_LOGFMT_PAIR}(?: {_LOGFMT_PAIR})*$")


def _assert_all_log_lines_match_logfmt(stderr: str) -> None:
    """Every line starting with ``level=`` must match NFR-10's logfmt
    grammar. Lines from C-level libs (``[ctranslate2]`` notice, Keras
    progress bar) don't start with ``level=`` and are silently skipped
    — out of NFR-10 scope per "tool's logging integration".
    """
    for line in stderr.splitlines():
        if not line.startswith("level="):
            continue
        assert _LOGFMT_LINE_RE.match(line), (
            f"NFR-10 violation: non-logfmt podcast_script log line: {line!r}"
        )
        assert " event=" in f" {line}", f"NFR-10 violation: missing event= key: {line!r}"

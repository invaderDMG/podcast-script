"""PTY / no-PTY harness for AC-US-3.1 + AC-US-3.2 (POD-035, US-3).

Tier 3 subprocess-level tests that validate the cli composition root's
TTY-sensing — the *only* place where the actual ``stderr.isatty()``
return value matters. In-process suites (``CliRunner``, ``StringIO``)
short-circuit this surface because their captured stderr is never a
real TTY; the SP-5 deliverable (PROJECT_PLAN §6) wants the asserted
behaviour exercised against a real subprocess.

Two narrow contracts:

* AC-US-3.1 — TTY stderr → :mod:`rich.progress` paints the three-phase
  progress bar with ANSI control sequences.
* AC-US-3.2 — non-TTY stderr (a regular pipe) → no ANSI; the
  line-per-phase plain-text fallback is the logfmt phase-boundary
  events the pipeline emits regardless of TTY state
  (``decode_done`` / ``segment_done`` / ``transcribe_done``).

Both tests run the full pipeline via ``faster-whisper --model tiny`` so
the TTY signal travels end-to-end (decoder → segmenter → backend →
write). Marked ``slow`` per ADR-0017; the Tier 3 CI job runs them on
Ubuntu + macOS-14.
"""

from __future__ import annotations

import os
import re
import select
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_MP3 = REPO_ROOT / "examples" / "sample.mp3"

# ESC ``[`` opens a CSI sequence — covers cursor moves, colour codes,
# and the ``\x1b[?25l`` hide-cursor that ``rich.progress`` writes at the
# top of its live region. A single CSI byte pair is sufficient signal:
# the user sees an ANSI-painted bar iff CSI escapes hit stderr.
_ANSI_CSI_RE = re.compile(rb"\x1b\[")
_PHASE_EVENT_RE = re.compile(rb"event=(?:decode_done|segment_done|transcribe_done)")
_DONE_EVENT_RE = re.compile(rb"event=done\b")
_LOGFMT_LEVEL_RE = re.compile(rb"^level=\w+ event=", re.MULTILINE)

# Generous budgets — first-run cold cache downloads the ~75 MB
# faster-whisper ``tiny`` model on a slow CI runner. Subsequent runs in
# the same job hit the warm cache and finish well under 30 s.
_PTY_TIMEOUT_S = 240.0
_PIPE_TIMEOUT_S = 240.0


@pytest.fixture(scope="module", autouse=True)
def _require_ffmpeg() -> None:
    """Skip the whole module if ffmpeg isn't installed (UC-1 E4)."""
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip(
            "ffmpeg not on PATH; required by C-Decode (UC-1 E4). "
            "Install via Homebrew (macOS) or apt (Ubuntu)."
        )


@pytest.fixture(scope="module")
def sample_mp3() -> Path:
    if not SAMPLE_MP3.exists():
        pytest.skip(
            "examples/sample.mp3 not on disk - run examples/build_sample.sh "
            "after dropping LibriVox + CC0 sources into examples/sources/ "
            "(POD-026)."
        )
    return SAMPLE_MP3


def _cli_argv(input_path: Path, output: Path) -> list[str]:
    """Build the argv for spawning the cli as a child process.

    Uses ``python -c "from podcast_script.cli import app; app()"`` so
    the test does not require the ``podcast-script`` console script to
    be on PATH — the same idiom works against a bare ``uv sync`` and
    against an editable install. ``app()`` reads ``sys.argv[1:]``, which
    under ``-c`` carries the user-typed arguments verbatim.
    """
    return [
        sys.executable,
        "-c",
        "from podcast_script.cli import app; app()",
        str(input_path),
        "--lang",
        "es",
        "--model",
        "tiny",
        "--backend",
        "faster-whisper",
        "-o",
        str(output),
    ]


def _drain_pty(master_fd: int, proc: subprocess.Popen[bytes], timeout: float) -> bytes:
    """Read from ``master_fd`` until the child exits; return all bytes.

    A naive ``proc.wait()`` then ``os.read`` deadlocks if the pty buffer
    fills before the child exits (~4 kB on Linux). The select loop
    drains the fd incrementally so the child never blocks on a stderr
    write.
    """
    captured = bytearray()
    deadline = time.monotonic() + timeout
    while True:
        if time.monotonic() > deadline:
            proc.kill()
            raise AssertionError(
                f"PTY harness exceeded {timeout:.0f} s; partial stderr={bytes(captured)!r}"
            )
        rlist, _, _ = select.select([master_fd], [], [], 0.2)
        if rlist:
            try:
                chunk = os.read(master_fd, 8192)
            except OSError:
                # Linux raises EIO once all writers have closed the slave.
                break
            if not chunk:
                break
            captured.extend(chunk)
            continue
        if proc.poll() is not None:
            # Child exited; drain any tail bytes the kernel still holds.
            try:
                while True:
                    chunk = os.read(master_fd, 8192)
                    if not chunk:
                        break
                    captured.extend(chunk)
            except OSError:
                pass
            break
    return bytes(captured)


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows is not a supported platform; pty.openpty is POSIX-only",
)
def test_pty_stderr_paints_ansi_progress_bar(sample_mp3: Path, tmp_path: Path) -> None:
    """AC-US-3.1 — TTY stderr → rich.Progress paints ANSI.

    Allocates a real PTY pair via :func:`pty.openpty` and binds the
    slave fd to the child's stderr. From the cli's point of view,
    ``sys.stderr`` is a TTY (``isatty()`` returns ``True``), so
    :func:`~podcast_script.progress.make_progress` drops out of the
    ``disable=True`` branch and rich emits CSI escape sequences for
    the live progress region. The parent reads the master fd and
    asserts CSI bytes appear in the captured stream alongside the
    three locked task descriptions.
    """
    import pty

    output = tmp_path / "sample_tiny.md"
    master_fd, slave_fd = pty.openpty()
    try:
        proc = subprocess.Popen(
            _cli_argv(sample_mp3, output),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=slave_fd,
        )
        os.close(slave_fd)
        captured = _drain_pty(master_fd, proc, _PTY_TIMEOUT_S)
    finally:
        os.close(master_fd)

    rc = proc.wait(timeout=10)
    assert rc == 0, f"cli exited {rc}; captured stderr={captured!r}"
    assert _ANSI_CSI_RE.search(captured), (
        f"expected ANSI CSI escapes from rich.Progress on a TTY stderr; captured={captured!r}"
    )
    # Spot-check the three named phases from AC-US-3.1 land in the
    # captured stream — rich prints the task descriptions as plain
    # bytes interleaved with the ANSI control bytes.
    for phase in (b"decode", b"segment", b"transcribe"):
        assert phase in captured, (
            f"missing {phase!r} task description in PTY-captured stderr; captured={captured!r}"
        )
    # The locked terminal summary (UC-1 step 10 / ADR-0012) still
    # lands on the same TTY-stderr the bar painted to.
    assert _DONE_EVENT_RE.search(captured), f"missing event=done summary; captured={captured!r}"


def test_piped_stderr_emits_no_ansi_with_phase_event_fallback(
    sample_mp3: Path, tmp_path: Path
) -> None:
    """AC-US-3.2 — non-TTY stderr → no ANSI; logfmt phase-boundary
    events are the line-per-phase fallback.

    A plain pipe (``stderr=subprocess.PIPE``) defeats ``isatty()``, so
    :func:`~podcast_script.progress.make_progress` returns a disabled
    bar and rich writes no progress bytes. The user-visible
    "line-per-phase plain-text update" is therefore the pipeline's own
    phase-boundary logfmt events (``decode_done`` / ``segment_done`` /
    ``transcribe_done``), which are emitted regardless of TTY state.
    """
    output = tmp_path / "sample_tiny.md"
    completed = subprocess.run(
        _cli_argv(sample_mp3, output),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=_PIPE_TIMEOUT_S,
    )
    assert completed.returncode == 0, (
        f"cli exited {completed.returncode}; stderr={completed.stderr!r}"
    )
    assert not _ANSI_CSI_RE.search(completed.stderr), (
        f"non-TTY stderr leaked ANSI CSI escapes from rich.Progress; stderr={completed.stderr!r}"
    )
    # AC-US-3.2 fallback: the three phase-boundary logfmt events stand
    # in for the live progress bar. Each phase's ``*_done`` line is
    # sufficient signal that the user got "one line per phase".
    matches = set(_PHASE_EVENT_RE.findall(completed.stderr))
    expected = {b"event=decode_done", b"event=segment_done", b"event=transcribe_done"}
    assert expected.issubset(matches), (
        f"missing phase-boundary fallback events; got={matches!r} stderr={completed.stderr!r}"
    )
    # Sanity — every podcast_script-emitted line on the piped stream
    # is well-formed logfmt (NFR-10) so a shell wrapper grepping by
    # ``event=`` keeps working without the bar to filter.
    assert _LOGFMT_LEVEL_RE.search(completed.stderr), (
        f"expected at least one logfmt level=...event=... line; stderr={completed.stderr!r}"
    )

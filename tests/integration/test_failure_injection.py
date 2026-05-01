"""Tier 3 failure-injection test (POD-034).

Pins NFR-5 (atomic output) and AC-US-6.3 (the previous output preserved
on transcribe failure) end-to-end, against a real subprocess. Tier 1
already covers the in-process exception path in
``tests/unit/test_atomic_write.py``; this module covers the
**signal-termination** path that no in-process test can reach.

The proof obligation here is the strongest form of NFR-5: when the CLI
is killed mid-transcribe (i.e. after segmentation completed and the
transcribe loop has begun, but before :func:`atomic_write` is reached),
**all three** of the following must hold:

1. The child exited non-zero (proves the kill arrived before
   ``_write`` completed; a clean exit would mean the kill was vacuous
   and the rest of the test would be a no-op).
2. No file exists at the resolved output path (atomic-rename contract,
   ADR-0005 — the only writer is :func:`atomic_write`, which is the
   final step of :meth:`Pipeline.run`).
3. No ``*.tmp`` debris in the output parent dir
   (:func:`atomic_write` is the only producer of ``.tmp`` files in
   that directory, and it only opens one near the very end of the
   pipeline; if a kill arrives during transcribe, no tempfile should
   ever have been created).

Together those three pin the design rather than just the implementation:
moving the ``atomic_write`` call earlier (so a tempfile lives during
transcribe) would fail assertion (3), and any refactor that wrote the
final Markdown directly to the target path would fail assertion (2).

We use **SIGTERM**, not SIGINT. ADR-0014 catches SIGINT at the cli
surface and converts it into a clean exit-1 path that runs Python
cleanup (atexit hooks, finally blocks). SIGTERM is uncaught: the
process dies immediately, no Python-level cleanup runs, and the only
thing keeping the target path clean is the design (no tempfile is ever
created before atomic_write opens one). That's a stronger test than
SIGINT.

The kill is timed against the locked ``event=transcribe_start``
phase-boundary token (ADR-0012 / 22-token catalogue, emitted by
:meth:`Pipeline._transcribe_speech` at line 222 of
``src/podcast_script/pipeline.py``). We tail the child's stderr in a
background reader thread so the main thread can SIGTERM as soon as
the line appears without risking deadlock on a partial-line read.

POSIX-only: ``signal.SIGTERM`` and the ``proc.terminate()`` semantics
this test relies on are POSIX. Windows is not a supported platform per
``PROJECT_BRIEF.md``; module-level skip mirrors the convention in
``test_tty_harness.py``.
"""

from __future__ import annotations

import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_MP3 = REPO_ROOT / "examples" / "sample.mp3"

_MISSING_FFMPEG_REASON = (
    "ffmpeg not on PATH; required by C-Decode (UC-1 E4). Install via "
    "Homebrew (macOS) or apt (Ubuntu)."
)
_MISSING_FIXTURE_REASON = (
    "examples/sample.mp3 not on disk - run examples/build_sample.sh "
    "after dropping LibriVox + CC0 sources into examples/sources/ "
    "(POD-026)."
)

# Allow up to 4 minutes for the child to reach event=transcribe_start.
# Cold-cache faster-whisper tiny download is ~75 MB (~30 s on a fresh
# CI runner); decode + segment add another ~10-20 s on the 60 s
# fixture. 240 s mirrors test_tty_harness.py's _PIPE_TIMEOUT_S.
_STARTUP_TIMEOUT_S = 240.0

# After SIGTERM, the child should exit within seconds. 30 s is generous;
# anything close to that bound likely indicates a deadlocked finalizer.
_KILL_TIMEOUT_S = 30.0


@pytest.fixture(scope="module", autouse=True)
def _require_ffmpeg() -> None:
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip(_MISSING_FFMPEG_REASON)


@pytest.fixture(scope="module")
def sample_mp3() -> Path:
    if not SAMPLE_MP3.exists():
        pytest.skip(_MISSING_FIXTURE_REASON)
    return SAMPLE_MP3


def _cli_argv(input_path: Path, output: Path) -> list[str]:
    """Spawn the cli without depending on the ``podcast-script`` console
    script being on PATH — same idiom as the PTY harness (POD-035)."""
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


def _stream_stderr_to_queue(stream: object, line_q: queue.Queue[str | None]) -> None:
    """Background reader: every stderr line goes onto ``line_q``; ``None``
    is the EOF sentinel.

    Running the readline loop on a thread keeps the main thread free to
    enforce the deadline and to terminate the child the moment
    ``event=transcribe_start`` appears, without risking a partial-line
    deadlock inside ``readline()``.
    """
    try:
        # ``stream`` is the ``proc.stderr`` text wrapper from Popen with
        # ``text=True``. Iterating ``readline`` until empty string is the
        # documented EOF idiom.
        readline = stream.readline  # type: ignore[attr-defined]
        for line in iter(readline, ""):
            line_q.put(line)
    finally:
        line_q.put(None)


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows is not a supported platform; SIGTERM semantics are POSIX",
)
def test_kill_during_transcribe_leaves_no_partial_output_NFR_5_AC_US_6_3(
    sample_mp3: Path, tmp_path: Path
) -> None:
    """Kill the CLI at ``event=transcribe_start``; assert no output, no
    tempfile, non-zero exit (NFR-5 / AC-US-6.3 end-to-end).
    """
    output_path = tmp_path / "episode.md"

    proc = subprocess.Popen(
        _cli_argv(sample_mp3, output_path),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        bufsize=1,
        text=True,
    )
    assert proc.stderr is not None  # for the type checker

    line_q: queue.Queue[str | None] = queue.Queue()
    reader = threading.Thread(
        target=_stream_stderr_to_queue,
        args=(proc.stderr, line_q),
        daemon=True,
    )
    reader.start()

    saw_transcribe_start = False
    captured_tail: list[str] = []
    deadline = time.monotonic() + _STARTUP_TIMEOUT_S

    try:
        while time.monotonic() < deadline:
            try:
                line = line_q.get(timeout=1.0)
            except queue.Empty:
                if proc.poll() is not None:
                    # Child exited before we could see the boundary
                    # event; fall through so the assertions below
                    # surface the early-exit failure mode clearly.
                    break
                continue
            if line is None:
                # EOF on stderr — child closed it. Drain in case the
                # writer queued more lines before the sentinel.
                break
            captured_tail.append(line)
            if len(captured_tail) > 50:
                captured_tail.pop(0)
            if "event=transcribe_start" in line:
                saw_transcribe_start = True
                proc.terminate()  # SIGTERM
                break
        else:
            proc.kill()
    finally:
        # Always reap; a leaked child would corrupt the next test's CI run.
        try:
            proc.wait(timeout=_KILL_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        reader.join(timeout=5)
        # Explicitly close the stderr pipe so the GC'd FileIO doesn't
        # raise ResourceWarning (which ``filterwarnings = ["error"]`` in
        # pyproject.toml upgrades to a hard failure). subprocess.Popen
        # doesn't auto-close parent-side pipes; the reader thread only
        # exhausts the iterator, it doesn't close the underlying fd.
        proc.stderr.close()

    # ---- Assertions ----
    # AC-1 (preconditions of the test itself — without these, the rest
    # is vacuous):
    assert saw_transcribe_start, (
        "never observed event=transcribe_start on stderr; the kill never "
        "happened mid-transcribe and the rest of this test would be "
        f"vacuous. Last stderr lines:\n{''.join(captured_tail)}"
    )
    assert proc.returncode != 0, (
        f"child exited cleanly (rc={proc.returncode}); SIGTERM arrived "
        "after the pipeline completed and atomic_write succeeded — "
        "kill was too late to actually inject a transcribe failure. "
        "Bump _STARTUP_TIMEOUT_S only if the test fixture grew; "
        "otherwise inspect why event=transcribe_start fired so late."
    )

    # AC-2 / AC-3 — the actual NFR-5 / AC-US-6.3 contract:
    assert not output_path.exists(), (
        f"{output_path} survived mid-transcribe kill — NFR-5 / AC-US-6.3 "
        "atomic-rename contract violated. The pipeline must only write "
        "the final Markdown via atomic_write at the very end of "
        "Pipeline.run()."
    )
    leaked_tmp = list(tmp_path.glob("*.tmp"))
    assert not leaked_tmp, (
        f"tempfile debris in {tmp_path}: {leaked_tmp}. The atomic_write "
        "helper (ADR-0005) is the only legitimate writer of *.tmp files "
        "in the output parent; mid-transcribe death predates that call, "
        "so no tempfile should ever exist."
    )

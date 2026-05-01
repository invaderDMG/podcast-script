"""Tier 3 integration tests (POD-029, ADR-0017).

Full CLI end-to-end against ``examples/sample.mp3`` (or the EC-3
non-ASCII fixture) with real ``ffmpeg``, real segmenter, real backend.
Marked ``pytest.mark.slow`` and skipped from the default suite — opt
in with ``pytest -m slow``. Also home to the PTY / no-PTY harness for
AC-US-3.1 + AC-US-3.2 (POD-035), which spawns the CLI under a real
``pty.openpty()`` to pin the ``stderr.isatty()`` sensing in the
composition root.

CI runs this tier on the Ubuntu + macOS-14 matrix per ADR-0017 — one
backend each (faster-whisper on Ubuntu, mlx-whisper on macOS).
"""

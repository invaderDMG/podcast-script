"""Atomic temp-then-rename writer (POD-009 / ADR-0005).

Owns the all-or-nothing write contract behind NFR-5 and AC-US-6.3: the
final Markdown either lands in full at the resolved output path, or the
path stays exactly as it was before the run started. The pipeline
orchestrator (POD-008, SP-2) is the only intended caller.
"""

from __future__ import annotations

import contextlib
import os
import stat
import tempfile
from pathlib import Path


def atomic_write(path: Path, content: str) -> None:
    """Atomically write ``content`` (UTF-8) to ``path``.

    A temp file is created in ``path.parent`` (so the rename is on the
    same filesystem and therefore atomic on POSIX per ADR-0005), the
    payload is written and ``fsync``-ed best-effort, then ``os.replace``
    promotes it to ``path``. If anything fails before the rename, the
    temp file is removed and any prior file at ``path`` is untouched.
    """
    payload = content.encode("utf-8")
    prior_mode: int | None = None
    with contextlib.suppress(FileNotFoundError):
        prior_mode = stat.S_IMODE(path.stat().st_mode)

    tmp_path: Path | None = None
    renamed = False
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=path.stem + ".",
            suffix=".md.tmp",
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(payload)
            tmp.flush()
            with contextlib.suppress(OSError):
                os.fsync(tmp.fileno())
        os.replace(tmp_path, path)
        renamed = True
    finally:
        if not renamed and tmp_path is not None:
            tmp_path.unlink(missing_ok=True)

    _fsync_directory_best_effort(path.parent)

    if prior_mode is not None:
        os.chmod(path, prior_mode)


def _fsync_directory_best_effort(directory: Path) -> None:
    """Flush ``directory``'s metadata so the preceding rename survives a
    power loss. Best-effort: any ``OSError`` (e.g. on filesystems that don't
    support directory fsync) is swallowed, mirroring the file-fsync policy
    in ADR-0005 §Consequences.
    """
    try:
        dir_fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        with contextlib.suppress(OSError):
            os.fsync(dir_fd)
    finally:
        os.close(dir_fd)

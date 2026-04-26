"""Logging configuration for podcast-script (ADR-0008 + NFR-10).

Wires the standard ``logging`` ``Logger`` through a ``RichHandler`` whose
``console`` is the live ``rich.progress.Progress.console`` (when one is
running) or a plain ``Console(stderr=True)`` otherwise — so the progress
UI and the log stream cooperate on the same TTY without tearing.

The on-stderr bytes are still logfmt (``key=value`` pairs); ``RichHandler``
is purely the rendering channel. NFR-10 holds because ``LogfmtFormatter``
owns the format, not Rich.

POD-003 ships the *initial cut*: the formatter, the configure-once helper,
and the console-selection rule. The 22-token frozen event catalogue is
enforced separately in POD-015.
"""

import logging


class LogfmtFormatter(logging.Formatter):
    """Render a ``LogRecord`` as a single logfmt line.

    Output shape: ``level=<lvl> event=<token> <key>=<value> ...``. ``level``
    is always first; ``event`` (if present as an ``extra`` attribute on the
    record) is always second so operators can grep one fixed position.
    """

    def format(self, record: logging.LogRecord) -> str:
        parts = [f"level={record.levelname.lower()}"]
        if hasattr(record, "event"):
            parts.append(f"event={record.event}")
        return " ".join(parts)

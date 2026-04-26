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
from typing import Literal

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress

Verbosity = Literal["quiet", "normal", "verbose", "debug"]
"""Verbosity selector accepted by :func:`configure`. The CLI flag plumbing
that maps ``-q``/``-v``/``--debug`` onto these labels lands in POD-014."""

_LEVEL_FOR_VERBOSITY: dict[Verbosity, int] = {
    "quiet": logging.ERROR,
    "normal": logging.INFO,
    "verbose": logging.DEBUG,
    "debug": logging.DEBUG,
}

_LOGGER_NAME = "podcast_script"

# Built-in ``LogRecord`` attribute names — anything else on ``__dict__`` is an
# ``extra=`` kwarg from the caller and gets rendered as a logfmt pair.
_STD_RECORD_KEYS = frozenset(
    {
        "args",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


class LogfmtFormatter(logging.Formatter):
    """Render a ``LogRecord`` as a single logfmt line.

    Output shape: ``level=<lvl> event=<token> <key>=<value> ...``. ``level``
    is always first; ``event`` (if present as an ``extra`` attribute on the
    record) is always second so operators can grep one fixed position. The
    remaining ``extra=`` kwargs follow in insertion order.
    """

    def format(self, record: logging.LogRecord) -> str:
        parts = [f"level={record.levelname.lower()}"]
        if hasattr(record, "event"):
            parts.append(f"event={_format_value(record.event)}")
        for key, value in record.__dict__.items():
            if key in _STD_RECORD_KEYS or key == "event":
                continue
            parts.append(f"{key}={_format_value(value)}")
        return " ".join(parts)


def _format_value(value: object) -> str:
    """Render ``value`` as a logfmt fragment.

    Bare when the string has no whitespace, ``=``, or ``"``. Otherwise
    wrapped in double quotes, with ``\\`` and ``"`` backslash-escaped.
    Empty strings are rendered as ``""`` (an unquoted empty would be
    indistinguishable from a missing value to a downstream parser).
    """
    s = str(value)
    needs_quoting = not s or any(ch in s for ch in (" ", "\t", "\n", "=", '"'))
    if not needs_quoting:
        return s
    escaped = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def configure(verbosity: Verbosity, progress: Progress | None) -> logging.Logger:
    """Wire the ``podcast_script`` logger per ADR-0008.

    Returns the configured logger so callers can pass it on; the function is
    idempotent — re-calling it replaces handlers rather than stacking them.
    """
    console = progress.console if progress is not None else Console(stderr=True)
    handler = RichHandler(console=console)

    logger = logging.getLogger(_LOGGER_NAME)
    logger.addHandler(handler)
    logger.setLevel(_LEVEL_FOR_VERBOSITY[verbosity])
    return logger

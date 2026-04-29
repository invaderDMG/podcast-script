"""CLI entrypoint for podcast-script (POD-006 + POD-016).

Owns the typer surface and the ADR-0006 exception → ``typer.Exit(code)``
translation. Per ADR-0006, this module is the *only* place that converts
:class:`PodcastScriptError` subclasses into exit codes; stages elsewhere
raise the typed exceptions and never call ``sys.exit`` directly.

The ``--lang`` curated set is locked at SRS §1.7 / Q11; the validator —
including the Levenshtein-≤-2 did-you-mean (AC-US-1.5) — lives in
:mod:`.config` and is re-exported here for backward compatibility with
callers that imported the cli helpers directly.

POD-016 inverts the previous "CLI wins implicitly" model: the CLI
collects each flag as ``None`` when the user didn't pass it, hands the
dict (plus the parsed TOML defaults from
:data:`~podcast_script.config.DEFAULT_CONFIG_PATH`) to
:func:`~podcast_script.config.merge`, and runs the pipeline against the
merged :class:`~podcast_script.config.Config`. Defaults (``model =
large-v3``, ``device = auto``, …) live in :mod:`.config`, not here, so
TOML can show through any flag the user didn't type (AC-US-4.1).

POD-008 wired :class:`~podcast_script.pipeline.Pipeline` behind
:func:`_run_pipeline`; the cli is the composition root that hands real
stages to the orchestrator (ADR-0002). Until POD-010 / POD-011 /
POD-018-020 land, the stub stages defined in this module produce a
placeholder Markdown body so the smoke path works end-to-end without
the heavy ML deps.
"""

from __future__ import annotations

import contextlib
import functools
import platform
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from . import config as _config
from .backends.base import select_backend
from .config import SUPPORTED_LANGS, validate_lang
from .errors import InputIOError, OutputExistsError, PodcastScriptError, UsageError
from .logging_setup import configure
from .pipeline import RunSummary
from .progress import Progress, make_progress

if TYPE_CHECKING:
    from .backends.base import WhisperBackend
    from .logging_setup import Verbosity

# Re-exported so existing imports (``from podcast_script.cli import
# SUPPORTED_LANGS, validate_lang``) keep working post-POD-016.
__all__ = ["SUPPORTED_LANGS", "app", "validate_lang"]

# Exit-code table required in --help by SRS §9.1 (line 430): "lists every
# flag, the eight supported --lang codes, AND the documented exit-code
# table (NFR-9)". Codes themselves are owned by the exception classes in
# errors.py per ADR-0006; this is the human-readable surface.
#
# The leading ``\b`` is Click's "do not reflow this paragraph" marker —
# required because Click otherwise rewraps the epilog into one run-on
# line. Typer renders this through Click when ``rich_markup_mode=None``.
_EXIT_CODE_EPILOG = (
    "\b\n"
    "Exit codes (NFR-9):\n"
    "  0  success\n"
    "  1  generic / unexpected internal error\n"
    "  2  usage error (bad flags, missing/unsupported --lang, ffmpeg not on PATH)\n"
    "  3  input I/O error (input not found, output parent missing)\n"
    "  4  decode error (ffmpeg failed)\n"
    "  5  model / network error\n"
    "  6  output exists without --force"
)

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    rich_markup_mode=None,
)


def _check_output_path(resolved_output: Path, *, force: bool) -> None:
    """Pre-flight gate for the resolved output path (POD-022, US-6).

    Two ACs are enforced before the pipeline starts so a misconfigured
    invocation costs nothing more than an exit code:

    * AC-US-6.4 — parent directory must already exist (the cli MUST NOT
      create it); raises :class:`InputIOError` (exit 3). Holds with or
      without ``--force``.
    * AC-US-6.1 — if the path already exists and ``--force``/``-f`` was
      not passed, raise :class:`OutputExistsError` (exit 6); the prior
      file is therefore left untouched.

    Order matters: a missing parent makes the existence check
    meaningless, so it is reported first and only then is overwrite
    refused.
    """
    parent = resolved_output.parent
    if not parent.is_dir():
        raise InputIOError(
            f"output parent directory does not exist: {parent}; "
            "create it before re-running, or pass -o/--output with an existing parent"
        )
    if resolved_output.exists() and not force:
        raise OutputExistsError(
            f"refusing to overwrite existing file {resolved_output}; pass --force / -f to opt in"
        )


def _gate_debug_dir(debug_dir: Path, *, force: bool) -> None:
    """ADR-0015 — refuse-without-``--force`` for the debug dir (POD-025).

    Mirrors :func:`_check_output_path`'s US-6 behaviour for the output
    Markdown so the user's mental model is single — ``--force`` is the
    only opt-in that destroys prior work, regardless of which artifact
    is on disk.

    * If ``debug_dir`` does not exist → no-op; the lazy ``mkdir`` in
      ``Pipeline._write_*`` handlers will create it on first write.
    * If it exists and ``force`` is False → :class:`OutputExistsError`
      (exit 6, ``event=output_exists``).
    * If it exists and ``force`` is True → ``shutil.rmtree`` + recreate
      so a partial run (e.g. one that died mid-transcribe) doesn't
      leak stale files into the new run's artifacts.
    """
    import shutil

    if not debug_dir.exists():
        return
    if not force:
        raise OutputExistsError(
            f"refusing to overwrite existing debug directory {debug_dir}; "
            "pass --force / -f to opt in (or omit --debug)"
        )
    shutil.rmtree(debug_dir)
    debug_dir.mkdir(parents=True)


def _resolve_verbosity(verbose: bool, quiet: bool, debug: bool) -> Verbosity:
    """Map the three flag booleans to a :data:`Verbosity` label.

    SRS §9.1 grammar — ``[-v, --verbose | -q, --quiet | --debug]`` —
    documents the three flags as mutually exclusive: at most one may
    be set. Combining any two is a :class:`UsageError` (exit 2 per
    ADR-0006). The cli enforces this guard *before* any pipeline work
    begins so a misconfigured invocation costs nothing more than an
    error message.

    Per AC-US-3.5, the resulting label drives the logger level via
    :data:`podcast_script.logging_setup._LEVEL_FOR_VERBOSITY`:

    * ``quiet``   — only ``level=error`` lines on stderr.
    * ``normal``  — ``level=info`` and above + progress bar.
    * ``verbose`` — ``level=debug`` and above + progress bar.
    * ``debug``   — same level as verbose plus the artifact dir of
      US-7 (POD-024 owns the dir-emission half).
    """
    chosen = sum((verbose, quiet, debug))
    if chosen > 1:
        raise UsageError(
            "--verbose (-v), --quiet (-q), and --debug are mutually exclusive; pass at most one"
        )
    if debug:
        return "debug"
    if verbose:
        return "verbose"
    if quiet:
        return "quiet"
    return "normal"


def _platform_tag() -> str:
    """Concise platform identifier for the ``event=backend_selected`` line.

    Format: ``<machine>-<sys.platform>`` (``arm64-darwin``,
    ``x86_64-linux``, …) — same convention as the E7 error in
    :func:`~podcast_script.backends.base.select_backend`, the SRS UC-1
    step 4 platform-detection rule, and ADR-0003. Once v1.0 ships, the
    value of this token is part of the implicit grep contract (Risk
    #9), so the surface stays consistent across error path + success
    path.
    """
    return f"{platform.machine()}-{sys.platform}"


def _run_pipeline(
    *,
    input_path: Path,
    output_path: Path,
    lang: str,
    model: str,
    backend_instance: WhisperBackend,
    device: str,
    progress: Progress | None,
    force: bool,
    debug_dir: Path | None,
) -> RunSummary:
    """Compose the pipeline and run it; return the cli-summary payload.

    The cli is the composition root (ADR-0002 §Decision step 4) — it
    instantiates the concrete stages and hands them to :class:`Pipeline`.
    Both ``backend_instance`` (via ``select_backend``) and ``progress``
    (via :func:`~podcast_script.progress.make_progress`) are resolved
    by ``main()`` so their lifecycle events (``backend_selected``) and
    log-handler-Console binding (ADR-0008) can be set up before the
    pipeline runs.

    POD-024 — when ``debug_dir`` is set we bind it into the ``decode``
    callable via :func:`functools.partial` so ``decode()`` writes
    ``commands.txt`` automatically (see :mod:`.decode`); the pipeline
    side handles the other three artifacts (decoded.wav,
    segments.jsonl, transcribe.jsonl) per AC-US-7.1.
    """
    del force

    from .decode import decode as decode_audio
    from .pipeline import Pipeline
    from .render import render
    from .segment import InaSpeechSegmenter

    decode_fn = (
        functools.partial(decode_audio, debug_dir=debug_dir)
        if debug_dir is not None
        else decode_audio
    )

    pipeline = Pipeline(
        decode=decode_fn,
        segmenter=InaSpeechSegmenter(),
        backend=backend_instance,
        render=render,
        model=model,
        device=device,
        lang=lang,
        progress=progress,
        debug_dir=debug_dir,
    )
    return pipeline.run(input_path=input_path, output_path=output_path)


@app.command(epilog=_EXIT_CODE_EPILOG)
def main(
    input_path: Annotated[
        Path,
        typer.Argument(
            metavar="INPUT",
            help="Audio file to transcribe (any format ffmpeg can decode).",
        ),
    ],
    lang: Annotated[
        str | None,
        typer.Option("--lang", help=f"Language code. One of: {', '.join(SUPPORTED_LANGS)}."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output",
            help="Output Markdown path. Defaults to <input-stem>.md next to the input.",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "-f", "--force", help="Overwrite an existing output file. Default refuses (exit 6)."
        ),
    ] = False,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            help=(
                "Whisper model: tiny|base|small|medium|large-v3|large-v3-turbo. Default: large-v3."
            ),
        ),
    ] = None,
    backend: Annotated[
        str | None,
        typer.Option(
            "--backend",
            help="Whisper backend: faster-whisper|mlx-whisper. Auto-selected by platform.",
        ),
    ] = None,
    device: Annotated[
        str | None,
        typer.Option("--device", help="Compute device: auto|cpu|cuda|mps. Default: auto."),
    ] = None,
    verbose: Annotated[
        bool, typer.Option("-v", "--verbose", help="Enable debug-level logs.")
    ] = False,
    quiet: Annotated[
        bool, typer.Option("-q", "--quiet", help="Suppress informational logs.")
    ] = False,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug", help="Retain intermediate artifacts in <input-stem>.debug/ (US-7)."
        ),
    ] = False,
) -> None:
    """Transcribe a podcast audio file to Markdown with music-segment markers."""
    # Pre-configure with a permissive default so a UsageError raised by
    # ``_resolve_verbosity`` (the SRS §9.1 mutual-exclusion guard) has a
    # working logger to route through the cli's catch-and-translate
    # handler. Re-configured with the resolved verbosity below if the
    # guard passes.
    verbosity: Verbosity = "normal"
    log = configure(verbosity, progress=None)
    wall_start = time.monotonic()

    try:
        verbosity = _resolve_verbosity(verbose, quiet, debug)
        log = configure(verbosity, progress=None)

        # ADR-0012 lifecycle — ``event=startup`` fires once argv has been
        # parsed by typer and before any work begins. Lets shell wrappers
        # see "tool started" before model load (which can take seconds
        # on a cold cache). Emitted under the resolved verbosity so
        # ``--quiet`` correctly drops it (AC-US-3.5).
        log.info("", extra={"event": "startup"})

        # POD-016 — load TOML defaults from the locked path (None = absent)
        # then merge with whatever the user typed on argv. ``cli_overrides``
        # carries every flag value as-is; entries with ``None`` mean
        # "user didn't pass this flag" and let TOML / built-in defaults
        # show through (AC-US-4.1). CLI values that *are* set win
        # (AC-US-4.2). Missing lang anywhere → AC-US-4.3.
        toml_defaults = _config.load_toml_defaults(_config.DEFAULT_CONFIG_PATH)
        cli_overrides: dict[str, object] = {
            "input": input_path,
            "output": output,
            "lang": lang,
            "model": model,
            "backend": backend,
            "device": device,
            "force": force,
            "verbosity": verbosity,
        }
        cfg = _config.merge(toml_defaults=toml_defaults, cli_overrides=cli_overrides)

        # ADR-0012 lifecycle — ``event=config_loaded`` fires after the
        # CLI + TOML merge resolves to a validated Config. Order matters:
        # ``startup`` → ``config_loaded`` → ``backend_selected`` →
        # (pipeline events) → ``done``.
        log.info("", extra={"event": "config_loaded"})

        # ADR-0012 lifecycle — ``event=backend_selected`` fires *before*
        # any heavy lib touches; the platform-detection rule (ADR-0003,
        # UC-1 E7) lives in ``select_backend``. Resolving the backend
        # here (not inside ``_run_pipeline``) lets the event surface
        # under any test that stubs ``_run_pipeline``.
        backend_instance = select_backend(backend=cfg.backend, device=cfg.device)
        log.info(
            "",
            extra={
                "event": "backend_selected",
                "backend": backend_instance.name,
                "device": cfg.device,
                "platform": _platform_tag(),
            },
        )

        resolved_output = cfg.output if cfg.output is not None else cfg.input.with_suffix(".md")
        _check_output_path(resolved_output, force=cfg.force)

        # POD-024 — when ``--debug`` is set, the artifact directory
        # lands at ``<input-stem>.debug/`` next to the input per
        # AC-US-7.1.
        # POD-025 / ADR-0015 — refuse-without-``--force`` gate. Mirrors
        # US-6's output-Markdown rule: never silently destroys prior
        # debug artifacts. Reuses ``OutputExistsError`` (exit 6,
        # ``event=output_exists``) so the catalogue stays at 22 tokens
        # (ADR-0012). With ``--force`` the prior dir is rmtree'd and
        # the run proceeds against a fresh empty directory.
        debug_dir = cfg.input.parent / f"{cfg.input.stem}.debug" if debug else None
        if debug_dir is not None:
            _gate_debug_dir(debug_dir, force=cfg.force)

        # POD-013 — three-phase progress bar (decode / segment /
        # transcribe). Hoisted up here (not inside ``_run_pipeline``)
        # so we can re-configure the log handler to share the Progress
        # console per ADR-0008 — keeps progress + log lines from
        # tearing on a real TTY. ``make_progress`` honours AC-US-3.2
        # by disabling itself on non-TTY stderr so pipe / CI captures
        # see no ANSI.
        #
        # ``--quiet`` constructs no Progress at all per ADR-0008
        # §Decision step 4 / AC-US-3.3 — POD-014 will lift this gate
        # once the full verbosity matrix lands. The ``with`` block
        # guarantees ``Progress.stop()`` even if the pipeline raises;
        # ``nullcontext()`` keeps the call shape symmetric on the
        # ``--quiet`` path.
        bar = make_progress() if verbosity != "quiet" else None
        log = configure(verbosity, progress=bar)
        with bar if bar is not None else contextlib.nullcontext():
            summary = _run_pipeline(
                input_path=cfg.input,
                output_path=resolved_output,
                lang=cfg.lang,
                model=cfg.model,
                backend_instance=backend_instance,
                device=cfg.device,
                progress=bar,
                force=cfg.force,
                debug_dir=debug_dir,
            )

        # SRS UC-1 step 10 — locked logfmt summary line.
        # Shape: ``level=info event=done input=<path> output=<path>
        # backend=<name> model=<name> lang=<code> duration_in_s=<n>
        # duration_wall_s=<n>``. Order is preserved by
        # :class:`~podcast_script.logging_setup.LogfmtFormatter` (insertion
        # order). Treated as part of the v1.0 grep contract per Risk #9.
        log.info(
            "",
            extra={
                "event": "done",
                "input": str(cfg.input),
                "output": str(resolved_output),
                "backend": backend_instance.name,
                "model": cfg.model,
                "lang": cfg.lang,
                "duration_in_s": f"{summary.duration_in_s:.3f}",
                "duration_wall_s": f"{time.monotonic() - wall_start:.3f}",
            },
        )
    except PodcastScriptError as exc:
        log.error("", extra={"event": exc.event, "code": exc.exit_code, "cause": str(exc)})
        raise typer.Exit(exc.exit_code) from exc
    except Exception as exc:
        log.error("", extra={"event": "internal_error", "code": 1, "cause": str(exc)})
        if verbosity == "debug":
            raise
        raise typer.Exit(1) from exc

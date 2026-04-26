"""CLI entrypoint for podcast-script (POD-006).

Owns the typer-based ``--lang`` validation surface and the ADR-0006
exception → ``typer.Exit(code)`` translation. Per ADR-0006, this module
is the *only* place that converts :class:`PodcastScriptError` subclasses
into exit codes; stages elsewhere raise the typed exceptions and never
call ``sys.exit`` directly.

The ``--lang`` curated set is locked at SRS §1.7 / Q11; unknown codes are
rejected with a "did you mean?" suggestion via Levenshtein distance ≤ 2
(AC-US-1.5). Missing ``--lang`` (and, once POD-016 lands, no config
fallback) is also a usage error (AC-US-4.3).

POD-008 wired :class:`~podcast_script.pipeline.Pipeline` behind
:func:`_run_pipeline`; the cli is the composition root that hands real
stages to the orchestrator (ADR-0002). Until POD-010 / POD-011 /
POD-018-020 land, the stub stages defined in this module produce a
placeholder Markdown body so the smoke path works end-to-end without
the heavy ML deps.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from .errors import PodcastScriptError, UsageError
from .logging_setup import Verbosity, configure

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

    from .backends.base import TranscribedSegment
    from .render import TimestampFormat
    from .segment import Segment

SUPPORTED_LANGS: tuple[str, ...] = ("es", "en", "pt", "fr", "de", "it", "ca", "eu")
"""The eight v1 ``--lang`` codes (SRS §1.7). Frozen for v1.0.0; expanding
this set is a SemVer-major event because it changes the CLI contract."""

_DID_YOU_MEAN_MAX_DISTANCE = 2
"""Per AC-US-1.5: suggest a code only when its Levenshtein distance to the
typo is ≤ 2. Larger distances would surface unrelated codes as 'suggestions'."""

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


def validate_lang(code: str) -> None:
    """Validate ``code`` against the curated v1 ``--lang`` set.

    Raises :class:`UsageError` (exit 2) if ``code`` is not in
    :data:`SUPPORTED_LANGS`. The error message lists all supported codes
    and, when the typo is within Levenshtein distance 2 of a supported
    code, appends a ``did you mean `<closest>`?`` suggestion.
    """
    if code in SUPPORTED_LANGS:
        return

    supported = ", ".join(SUPPORTED_LANGS)
    suggestion = _closest_supported_lang(code)
    base = f"unknown --lang {code!r}; supported: {supported}"
    if suggestion is not None:
        raise UsageError(f"{base}; did you mean `{suggestion}`?")
    raise UsageError(base)


def _missing_lang_error() -> UsageError:
    supported = ", ".join(SUPPORTED_LANGS)
    return UsageError(f"--lang is required (e.g. --lang es). Supported: {supported}")


def _closest_supported_lang(code: str) -> str | None:
    """Return the closest supported code within ≤ 2 edits, or ``None``.

    Ties are broken by :data:`SUPPORTED_LANGS` order — i.e. ``es`` wins
    over ``en`` if both are equidistant — which makes the suggestion
    deterministic across runs.
    """
    best: tuple[int, str] | None = None
    for candidate in SUPPORTED_LANGS:
        distance = _levenshtein(code, candidate)
        if distance > _DID_YOU_MEAN_MAX_DISTANCE:
            continue
        if best is None or distance < best[0]:
            best = (distance, candidate)
    return best[1] if best is not None else None


def _levenshtein(a: str, b: str) -> int:
    """Standard Levenshtein edit distance.

    Implemented inline rather than via a third-party ``rapidfuzz``-style
    dep because ADR-0013 forbids new runtime deps for v1; the cost on
    2-to-~8-character strings is negligible.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            substitute = previous[j - 1] + (ca != cb)
            current.append(min(insert, delete, substitute))
        previous = current
    return previous[-1]


def _resolve_verbosity(verbose: bool, quiet: bool, debug: bool) -> Verbosity:
    """Map the three flag booleans to a :data:`Verbosity` label.

    Mutual-exclusion enforcement and a richer matrix land in POD-014
    (SP-5); for POD-006 we just pick the strongest signal so log output
    behaves consistently when more than one is passed by accident.
    """
    if debug:
        return "debug"
    if verbose:
        return "verbose"
    if quiet:
        return "quiet"
    return "normal"


class _StubBackend:
    """Placeholder ``WhisperBackend`` until POD-018/019/020 land.

    No model is loaded; ``transcribe`` returns nothing. The smoke-test
    end-to-end pipeline therefore writes a body with no speech lines —
    enough to exercise the orchestrator + decode + atomic write before
    the real backends arrive in SP-3 / SP-4.
    """

    name = "stub"

    def load(self, model: str, device: str) -> None:
        del model, device

    def transcribe(
        self,
        pcm: npt.NDArray[np.float32],
        lang: str,
        sample_rate: int = 16_000,
    ) -> Iterable[TranscribedSegment]:
        del pcm, lang, sample_rate
        return ()


class _StubSegmenter:
    """Placeholder ``Segmenter`` until POD-010 lands.

    Returns a single ``speech`` segment covering the full decoded
    duration so the orchestrator's transcribe loop runs once and the
    streaming-contract code path is exercised end-to-end.
    """

    def segment(self, pcm: npt.NDArray[np.float32]) -> list[Segment]:
        from .segment import Segment

        duration_s = len(pcm) / 16_000
        return [Segment(start=0.0, end=duration_s, label="speech")]


def _stub_render(
    segments: list[Segment],
    transcripts: list[TranscribedSegment],
    fmt: TimestampFormat,
) -> str:
    """Placeholder Markdown body until POD-011 lands.

    Emits enough structure that AC-US-1.1 ("the tool writes ``episode.md``
    next to the input and exits with code 0") holds at the smoke level;
    the locked output shape (SRS §1.6) lands with POD-011.
    """
    del segments, transcripts
    return f"# transcript (stub renderer; POD-011 ships the real shape)\n\nfmt={fmt}\n"


def _run_pipeline(
    *,
    input_path: Path,
    output_path: Path,
    lang: str,
    model: str,
    backend: str | None,
    device: str,
    force: bool,
    debug: bool,
) -> None:
    """Compose the pipeline and run it.

    The cli is the composition root (ADR-0002 §Decision step 4) — it
    instantiates the concrete stages and hands them to :class:`Pipeline`.
    Real stages plug in as their tasks land: ``Segmenter`` (POD-010),
    ``render`` (POD-011), ``WhisperBackend`` + ``select_backend``
    (POD-018/019/020). ``--force`` / ``--debug`` wiring lands in
    POD-022/023 / POD-024 respectively; for POD-008 they're accepted but
    inert beyond reaching the orchestrator.
    """
    del backend, force, debug

    from .decode import decode as decode_audio
    from .pipeline import Pipeline

    pipeline = Pipeline(
        decode=decode_audio,
        segmenter=_StubSegmenter(),
        backend=_StubBackend(),
        render=_stub_render,
        model=model,
        device=device,
        lang=lang,
    )
    pipeline.run(input_path=input_path, output_path=output_path)


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
        str,
        typer.Option(
            "--model", help="Whisper model: tiny|base|small|medium|large-v3|large-v3-turbo."
        ),
    ] = "large-v3",
    backend: Annotated[
        str | None,
        typer.Option(
            "--backend",
            help="Whisper backend: faster-whisper|mlx-whisper. Auto-selected by platform.",
        ),
    ] = None,
    device: Annotated[
        str, typer.Option("--device", help="Compute device: auto|cpu|cuda|mps.")
    ] = "auto",
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
    verbosity = _resolve_verbosity(verbose, quiet, debug)
    log = configure(verbosity, progress=None)

    try:
        if lang is None:
            raise _missing_lang_error()
        validate_lang(lang)

        resolved_output = output if output is not None else input_path.with_suffix(".md")
        _run_pipeline(
            input_path=input_path,
            output_path=resolved_output,
            lang=lang,
            model=model,
            backend=backend,
            device=device,
            force=force,
            debug=debug,
        )
    except PodcastScriptError as exc:
        log.error("", extra={"event": exc.event, "code": exc.exit_code, "cause": str(exc)})
        raise typer.Exit(exc.exit_code) from exc
    except Exception as exc:
        log.error("", extra={"event": "internal_error", "code": 1, "cause": str(exc)})
        if verbosity == "debug":
            raise
        raise typer.Exit(1) from exc

"""CLI entrypoint for podcast-script (POD-006).

Owns the typer-based ``--lang`` validation surface. Per ADR-0006, this
module is the *only* one that translates :class:`PodcastScriptError`
subclasses into ``typer.Exit`` codes; stages elsewhere raise the typed
exceptions and never call ``sys.exit`` directly.

The ``--lang`` curated set is locked at SRS §1.7 / Q11; unknown codes are
rejected with a "did you mean?" suggestion via Levenshtein distance ≤ 2
(AC-US-1.5).
"""

from __future__ import annotations

import typer

from .errors import UsageError

app = typer.Typer()

SUPPORTED_LANGS: tuple[str, ...] = ("es", "en", "pt", "fr", "de", "it", "ca", "eu")
"""The eight v1 ``--lang`` codes (SRS §1.7). Frozen for v1.0.0; expanding
this set is a SemVer-major event because it changes the CLI contract."""

_DID_YOU_MEAN_MAX_DISTANCE = 2
"""Per AC-US-1.5: suggest a code only when its Levenshtein distance to the
typo is ≤ 2. Larger distances would surface unrelated codes as 'suggestions'."""


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

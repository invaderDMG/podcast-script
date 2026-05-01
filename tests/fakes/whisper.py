"""``FakeBackend`` — reusable test double for :class:`WhisperBackend` (POD-030).

Implements the ADR-0003 Protocol with no heavy library imports so Tier 2
contract tests can compare its behaviour against the real backends
without paying any cold-import cost. The same class is the "F" in the
parametrized ``[FakeBackend, FasterWhisperBackend, MlxWhisperBackend]``
contract suite — keeping it single-source prevents drift between the
test-only fake and any future reimplementation.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator, Sequence

import numpy as np
import numpy.typing as npt

from podcast_script.backends.base import (
    TranscribedSegment,
    emit_first_run_notice_if_missing,
)
from podcast_script.errors import ModelError

_log = logging.getLogger(__name__)

_DEFAULT_CANNED: tuple[TranscribedSegment, ...] = (
    TranscribedSegment(start=0.0, end=1.5, text="hola"),
    TranscribedSegment(start=1.5, end=3.0, text="qué tal"),
)


class FakeBackend:
    """In-memory :class:`WhisperBackend` for the contract suite."""

    name = "fake-whisper"

    def __init__(
        self,
        *,
        canned: Sequence[TranscribedSegment] | None = None,
        load_failure: BaseException | None = None,
        cache_miss: bool = False,
        load_delay_s: float = 0.0,
    ) -> None:
        self._canned: tuple[TranscribedSegment, ...] = (
            tuple(canned) if canned is not None else _DEFAULT_CANNED
        )
        self._load_failure = load_failure
        self._cache_miss = cache_miss
        self._load_delay_s = load_delay_s
        self._loaded = False

    def load(self, model: str, device: str) -> None:
        del device
        if self._loaded:
            return
        if self._cache_miss:
            emit_first_run_notice_if_missing(
                model,
                is_cached=lambda _m: False,
                logger=_log,
            )
        if self._load_failure is not None:
            failure = self._load_failure
            try:
                raise failure
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as e:
                raise ModelError(
                    f"Failed to load fake-whisper model '{model}': {type(e).__name__}: {e}"
                ) from e
        if self._load_delay_s > 0:
            time.sleep(self._load_delay_s)
        self._loaded = True

    def transcribe(
        self,
        pcm: npt.NDArray[np.float32],
        lang: str,
        sample_rate: int = 16000,
    ) -> Iterator[TranscribedSegment]:
        del lang, sample_rate
        if not self._loaded:
            raise ModelError(
                "FakeBackend.transcribe() called before load(); "
                "the orchestrator must call load() first per ADR-0009."
            )
        if pcm.size == 0:
            return iter(())
        return iter(self._canned)


__all__ = ["FakeBackend"]

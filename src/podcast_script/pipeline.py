"""Pipeline orchestrator (POD-008) — implementation lands in the next commit.

Stub for the failing-test commit per the TDD workflow: the class exists so
:mod:`tests.test_pipeline` imports without ``ModuleNotFoundError``, but
:meth:`Pipeline.run` doesn't do the work yet so the ACs fail at the
assertion boundary rather than at the import boundary.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

from .backends.base import WhisperBackend
from .render import RenderFn
from .segment import Segmenter

DecodeFn = Callable[[Path], npt.NDArray[np.float32]]


@dataclass
class Pipeline:
    """Pipes-and-filters orchestrator (ADR-0002)."""

    decode: DecodeFn
    segmenter: Segmenter
    backend: WhisperBackend
    render: RenderFn
    model: str
    device: str
    lang: str
    sample_rate: int = 16_000

    def run(self, *, input_path: Path, output_path: Path) -> None:
        raise NotImplementedError("POD-008 implementation pending")

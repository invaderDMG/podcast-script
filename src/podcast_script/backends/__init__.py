"""Whisper backend package (ADR-0003).

The :class:`WhisperBackend` Protocol and :class:`TranscribedSegment` live in
:mod:`.base`. Concrete implementations (``faster.py``, ``mlx.py``) land in
POD-019 / POD-020 with lazy imports per ADR-0011.
"""

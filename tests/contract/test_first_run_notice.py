"""Tier 2 contract test for the R-14 first-run-notice latency budget.

The contract under test (POD-030, ADR-0017 §Tier 2; mitigation for
PROJECT_PLAN §10.1 R-14): on a synthetic cache miss every backend's
:meth:`load` MUST emit the locked ``event=model_download`` line
**within 1 s** of ``load()`` entry, regardless of how slow the
underlying ``huggingface_hub`` download path turns out to be on a
given run. AC-US-5.1 states the requirement; ADR-0012 owns the line
shape; NFR-6 sets the 1-s budget.

The synthetic-cache-miss factory in :mod:`tests.contract.conftest`
inserts an artificial delay inside ``_build_model`` so the test is
meaningful: the notice's emission time is measured against the real
clock from ``load()`` entry, and a backend that buried the notice
behind the slow path would fail the budget.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import pytest

from tests.contract.conftest import CacheMissBackendFactory

# Synthetic build delay — short enough to keep the suite quick, long
# enough that the ordering check ("notice precedes build") has slack to
# fail meaningfully. Bumped from 0.5 s so the helper-overhead margin
# below leaves room for slower CI runners.
_SYNTHETIC_BUILD_DELAY_S = 0.8

# The R-14 / NFR-6 budget — also AC-US-5.1's "within 1 s of process start".
_NOTICE_BUDGET_S = 1.0

# Margin between "notice fired" and "build started". Empirically the
# helper + lazy-import + monkeypatched-method dispatch settles in
# < 100 ms on a modern laptop and < 200 ms on a cold GitHub Actions
# runner. Used to set the strict ordering threshold below the synthetic
# build delay so a backend that emits the notice after the slow path
# fails the check even when total wall time stays under 1 s.
_NOTICE_HELPER_OVERHEAD_S = 0.3


def _capture_records() -> tuple[
    logging.Handler,
    list[logging.LogRecord],
    Callable[[], None],
]:
    """Attach a model_download-only recording handler at the root logger.

    Each backend writes its model_download record to its own module-level
    logger (``podcast_script.backends.faster`` / ``…mlx`` for the real
    backends, ``tests.fakes.whisper`` for FakeBackend). The CLI's
    :func:`logging_setup.configure` is not in effect under pytest, so the
    contributing loggers inherit their level from root — which defaults
    to WARNING and would drop the INFO-level notice before propagation.

    We bump root to INFO for the duration of the test, attach a filtering
    handler that only records records with ``event=model_download`` (so
    third-party INFO chatter from the real backends' lazy imports stays
    out of the captured list), and return a teardown callable that
    restores the previous level.
    """
    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if getattr(record, "event", None) == "model_download":
                records.append(record)

    root = logging.getLogger()
    handler = _Capture()
    handler.setLevel(logging.INFO)
    root.addHandler(handler)
    prior_level = root.level
    if prior_level == logging.NOTSET or prior_level > logging.INFO:
        root.setLevel(logging.INFO)

    def _teardown() -> None:
        root.removeHandler(handler)
        root.setLevel(prior_level)

    return handler, records, _teardown


@pytest.mark.contract
def test_first_run_notice_fires_within_one_second_of_load_entry(
    cache_miss_backend_factory: CacheMissBackendFactory,
) -> None:
    """R-14 contract: notice's wall-clock emission MUST trail load()
    entry by less than 1 s, even when the underlying build path takes
    longer.

    The synthetic ``_SYNTHETIC_BUILD_DELAY_S`` (0.5 s) sleep inside
    ``_build_model`` simulates a slow HF download. A backend that
    emitted the notice after ``_build_model`` returned would clock in
    at ~0.5 s + helper overhead — the assertion below is engineered so
    a regression of that shape is detectable within budget.
    """
    _handler, records, teardown = _capture_records()

    backend = cache_miss_backend_factory(_SYNTHETIC_BUILD_DELAY_S)

    t_start_wall = time.time()
    try:
        backend.load(model="tiny", device="cpu")
    finally:
        teardown()

    notices = [r for r in records if getattr(r, "event", None) == "model_download"]
    assert len(notices) == 1, (
        f"AC-US-5.1: exactly one model_download record expected on a cache "
        f"miss (got {len(notices)}: {[getattr(r, 'event', None) for r in records]})"
    )
    notice = notices[0]

    elapsed_to_notice = notice.created - t_start_wall

    # Formal R-14 / NFR-6 / AC-US-5.1 budget — the published 1-s contract.
    assert elapsed_to_notice < _NOTICE_BUDGET_S, (
        f"R-14 / NFR-6 / AC-US-5.1: model_download notice MUST fire within "
        f"{_NOTICE_BUDGET_S} s of load() entry. Got {elapsed_to_notice:.3f} s "
        f"with synthetic build delay of {_SYNTHETIC_BUILD_DELAY_S} s."
    )

    # Stricter assertion: the notice MUST precede the slow build path by
    # a comfortable margin. This is what makes the synthetic build delay
    # carry signal — a backend that emitted the notice AFTER `_build_model`
    # returned would clock in at ~build_delay + helper overhead, failing
    # this check even though it might still squeak under the formal 1-s
    # budget for short delays. Mutation-tested locally by moving the
    # `emit_first_run_notice_if_missing` call below the sleep in
    # FakeBackend.load — the assertion catches it.
    notice_must_precede_build_by = _SYNTHETIC_BUILD_DELAY_S - _NOTICE_HELPER_OVERHEAD_S
    assert elapsed_to_notice < notice_must_precede_build_by, (
        f"AC-US-5.1 ordering: model_download notice MUST fire BEFORE the "
        f"slow build path (it is the user's signal that a multi-GB download "
        f"is starting, not a post-hoc receipt). Synthetic build_delay was "
        f"{_SYNTHETIC_BUILD_DELAY_S} s; notice fired {elapsed_to_notice:.3f} s "
        f"in — should be < {notice_must_precede_build_by:.3f} s."
    )

    # Sanity: the synthetic build delay actually elapsed, so the
    # ordering check above was meaningful (it had room to fail). If the
    # backend short-circuits the build path, we lose the R-14 signal.
    total_elapsed = time.time() - t_start_wall
    assert total_elapsed >= _SYNTHETIC_BUILD_DELAY_S * 0.8, (
        f"sanity: synthetic build_delay={_SYNTHETIC_BUILD_DELAY_S} s should "
        f"make load() take roughly that long; got {total_elapsed:.3f} s"
    )

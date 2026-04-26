"""Skeleton smoke test: package imports and exposes a version string."""

import podcast_script


def test_package_exposes_version_string() -> None:
    assert isinstance(podcast_script.__version__, str)
    assert podcast_script.__version__

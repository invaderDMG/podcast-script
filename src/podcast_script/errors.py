"""Typed exception hierarchy per ADR-0006. STUB — values land in the next commit."""


class PodcastScriptError(Exception):
    exit_code: int = 0
    event: str = ""


class UsageError(PodcastScriptError):
    pass


class InputIOError(PodcastScriptError):
    pass


class DecodeError(PodcastScriptError):
    pass


class ModelError(PodcastScriptError):
    pass


class OutputExistsError(PodcastScriptError):
    pass

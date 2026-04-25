# ADR-0013: Config implementation — stdlib `tomllib` + `dataclasses.dataclass`

- **Status:** Accepted
- **Date:** 2026-04-25
- **Deciders:** Solo maintainer
- **Supersedes:** —

## Context
`SRS.md` US-4 + AC-US-4.1..4.4 require a config file at `~/.config/podcast-script/config.toml` whose values pre-fill any CLI flag, with CLI flags winning on conflict and the same `--lang` validation rules applying whether the value comes from CLI or TOML.

The Config object is small: ~8 fields (`input`, `output`, `lang`, `model`, `backend`, `device`, `force`, `verbosity`), all primitive types or paths. `SRS.md` §1.3 explicitly excludes from v1: environment-variable overrides, JSON-shaped log output, and any "remote" config story. `PROJECT_BRIEF.md` §5 commits to Python 3.12+, so stdlib `tomllib` is available.

## Decision
Use **stdlib `tomllib` + `dataclasses.dataclass`** for the Config object and merge logic, with manual validation in `config.py`:

```python
# config.py (sketch)
from dataclasses import dataclass, replace
from pathlib import Path
import tomllib

@dataclass(frozen=True, slots=True)
class Config:
    input: Path
    output: Path | None
    lang: str
    model: str
    backend: str       # "auto" | "faster-whisper" | "mlx-whisper"
    device: str        # "auto" | "cpu" | "cuda" | "mps"
    force: bool
    verbosity: Verbosity  # Literal["quiet", "default", "verbose", "debug"]

def load_toml_defaults(path: Path) -> dict:
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text("utf-8"))

def merge(toml_defaults: dict, cli_overrides: dict) -> Config:
    # CLI wins on every conflict (AC-US-4.2)
    merged = {**toml_defaults, **{k: v for k, v in cli_overrides.items() if v is not None}}
    cfg = Config(**merged)
    validate(cfg)  # raises UsageError(exit 2) on bad lang/model/backend/device
    return cfg
```

Validation is a single function that:
1. Checks `lang ∈ SUPPORTED_LANGS` (the eight from SRS §1.7); on miss, computes Levenshtein-≤-2 candidates and raises `UsageError` with a "did you mean?" message (`SRS.md` AC-US-1.5, AC-US-4.4).
2. Checks `model ∈ {"tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"}`.
3. Checks `backend ∈ {"auto", "faster-whisper", "mlx-whisper"}`.
4. Checks `device ∈ {"auto", "cpu", "cuda", "mps"}`.
5. Coerces `Path`-typed fields with `Path(str).expanduser().resolve()`.

The whole module fits in ~120 LOC.

## Alternatives considered
- **`pydantic-settings`** — rejected: declarative validation, env-var binding, JSON Schema export. Real value in larger projects; here it adds a heavy dep tree (Pydantic, pydantic-core Rust binary, pydantic-settings) for ~8 scalar fields, and its main value-add (env-var binding) is explicitly out of scope per `SRS.md` §1.3.
- **`attrs` + `cattrs`** — rejected: `attrs` is slightly more ergonomic than dataclasses for slot/frozen/converter use, but the gap closed considerably with `dataclass(frozen=True, slots=True)` in 3.10+. One extra dep for marginal benefit at this size.
- **Hand-rolled `dict`-based config** (no dataclass) — rejected: loses static typing; mypy would flag every access; defeats `SRS.md` NFR-8's `mypy --strict` rule.

## Consequences
- **Positive:** zero new runtime deps; `mypy --strict` clean; `Config` is immutable (`frozen=True`) which prevents accidental mutation across stages; validation is one readable block of code; `dataclasses.replace(cfg, …)` makes it trivial to write CLI-override-merge tests.
- **Negative:** validation is hand-written, not declarative — adding a new field requires updating both the dataclass and `validate()`. At 8 fields with low churn, acceptable. If config grows past ~20 fields, revisit pydantic-settings.
- **Neutral:** the dataclass pattern is widely understood; future contributors find it without docs.

## Related
- ADR-0006 (typed exceptions — `UsageError` raised by `validate()`)
- ADR-0007 (module layout — `config.py` lives at the package root)
- `SRS.md` US-4, AC-US-4.1, AC-US-4.2, AC-US-4.3, AC-US-4.4, AC-US-1.5, §1.3 (env-var overrides Won't), §1.7
- `SYSTEM_DESIGN.md` §2.3 (C-Config)

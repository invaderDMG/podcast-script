# ADR-0001: ADR format — Michael Nygard

- **Status:** Accepted
- **Date:** 2026-04-25
- **Deciders:** Solo maintainer
- **Supersedes:** —

## Context
This project produces ADRs as the canonical record of load-bearing architectural decisions (see `SYSTEM_DESIGN.md` and the `system-design` skill). A format must be chosen before any other ADR is written, since every subsequent ADR will inherit it.

The project is small (solo maintainer, public GitHub repo, MIT, no enterprise governance — `PROJECT_BRIEF.md` §17), the rest of the documentation is intentionally lightweight (`docs/ARCHITECTURE.md` is a four-bullet one-pager per SRS §16.2, README is brief-style), and `CHANGELOG.md` follows Keep-a-Changelog. ADRs that are heavier than the surrounding docs would feel out-of-place and tend to rot.

## Decision
Use the **Michael Nygard** ADR format: `Status / Context / Decision / Alternatives considered / Consequences / Related`. One file per decision under `docs/adr/NNNN-kebab-case-slug.md`. Numbering is monotonic and never reused; superseded ADRs stay on disk with a `Status: Superseded by NNNN` line.

## Alternatives considered
- **MADR 4.0** — adds explicit decision drivers and a per-option pros/cons matrix. Rejected: the extra structure buys little for a solo maintainer; the Nygard "Alternatives considered" bullets already capture the trade-off trail without a table.
- **Custom format** — rejected: no existing convention in this repo to match, and inventing a format adds a learning step for any future contributor.

## Consequences
- **Positive:** ADRs stay short (<100 lines typical); render in any Markdown viewer; future contributors recognize the format from countless other projects.
- **Negative:** less structured than MADR — readers who want a strict "decision drivers vs. options" table won't get one.
- **Neutral:** the `Related` section is the conventional place to chain this ADR to SRS / `SYSTEM_DESIGN.md` IDs.

## Related
- `SYSTEM_DESIGN.md` §6 ADR index
- `docs/adr/README.md` index table

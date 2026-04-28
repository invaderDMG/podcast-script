# Credits — `examples/sample.mp3`

This file records the exact sources used to build the bundled
`examples/sample.mp3` test fixture (SRS §14.1). The raw sources are
archived under `examples/sources/` with SHA-256 checksums in
`examples/sources/CHECKSUMS.txt`, mitigating Risk **R-15**
(PROJECT_PLAN §10.3): if a source URL goes 404 post-v1.0.0, the bytes
that produced our fixture are still in the repo.

## Speech track

- **Title:** _to be filled in by Phase 2_
- **Reader:** _to be filled in_
- **Source URL:** _to be filled in_
- **License:** Public Domain (LibriVox catalog policy)
- **Retrieved:** _YYYY-MM-DD_
- **Local copy:** `examples/sources/speech.<ext>` (checksum in
  `examples/sources/CHECKSUMS.txt`)
- **Segment used:** the first ~60 s of the linked recording, trimmed
  inside `build_sample.sh` (no external editing).

## Music bed

- **Title:** _to be filled in_
- **Author:** _to be filled in_
- **Source URL:** _to be filled in_
- **License:** _CC0 1.0 / Public Domain — to be filled in with the exact
  license URL at-time-of-bundle_
- **Retrieved:** _YYYY-MM-DD_
- **Local copy:** `examples/sources/music.<ext>` (checksum in
  `examples/sources/CHECKSUMS.txt`)
- **Segment used:** the first ~10 s of the linked recording, mixed at
  -12 dB at 25–35 s of the speech track.

## Build recipe

`examples/sample.mp3` is rendered by:

```sh
./examples/build_sample.sh
```

which trims, mixes, and re-encodes the two sources per the SRS §14.1
spec (~60 s mono 16 kHz MP3, music bed bookended by speech, ≤ 1 MB).
The script is deterministic; re-running it on different hardware
produces a byte-identical `sample.mp3`.

## Adding a new language fixture

Per SRS §14.1, the unit of work to add a new code from `--lang` §1.7 is
to drop a public-domain speech sample for that language under
`examples/sources/<code>/speech.<ext>` (and reuse the existing music
bed) and copy `build_sample.sh` to a per-language variant. The
attribution table above expands accordingly.

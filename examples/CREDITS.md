# Credits — `examples/sample.mp3`

This file records the exact sources used to build the bundled
`examples/sample.mp3` test fixture (SRS §14.1). The raw sources are
archived under `examples/sources/` with SHA-256 checksums in
`examples/sources/CHECKSUMS.txt`, mitigating Risk **R-15**
(PROJECT_PLAN §10.3): if a source URL goes 404 post-v1.0.0, the bytes
that produced our fixture are still in the repo.

## Speech track

- **Title:** _Las Fábulas de Esopo, vol. 01_ — fable 002, "El águila y
  el escarabajo" ("The Eagle and the Beetle")
- **Author:** Aesop, Spanish translation by Jorge R. Rodríguez (after
  Townsend)
- **Reader:** LibriVox volunteer narrator (single solo voice on this
  track)
- **Source page:** https://archive.org/details/fabulas_esopo_01_librivox
  (catalog mirror: https://librivox.org/las-fabulas-de-esopo-vol-01/)
- **License:** Public Domain — LibriVox standard. The archive.org page
  states "Usage: Public Domain" and links to CC0 1.0 Universal:
  https://creativecommons.org/publicdomain/zero/1.0/
- **Retrieved:** 2026-04-28 (UTC)
- **Local copy:** `examples/sources/speech.mp3` — checksum recorded in
  `examples/sources/CHECKSUMS.txt`
- **Segment used:** the first 60 s of the linked recording (the full
  track is ~2:31), trimmed inside `build_sample.sh` (no external
  editing).

## Music bed

- **Title:** _Prelude Op. 28 No. 5_, by Frédéric Chopin
- **Performer:** Solo piano, from the Musopen Complete Chopin Collection
  curated by Aaron Dunn (Musopen)
- **Source page:** https://archive.org/details/musopen-chopin
- **License:** CC0 1.0 Universal — explicitly stated on the
  archive.org page. License URL:
  https://creativecommons.org/publicdomain/zero/1.0/
- **Retrieved:** 2026-04-28 (UTC)
- **Local copy:** `examples/sources/music.mp3` — checksum recorded in
  `examples/sources/CHECKSUMS.txt`
- **Segment used:** the first 10 s of the linked recording, used as a
  bookended music bed at 25-35 s — speech occupies 0-25 s and 35-60 s
  with the music alone in between (mixing the bed *under* speech
  caused the segmenter to label the music as `speech` per SRS Risk #3).

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

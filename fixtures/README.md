# Fixture corpus — deliberately malicious, do not execute

Every directory under `fixtures/` is a **hand-built attack fixture**. The files named
`vulnerable` in `manifest.yaml` contain working attack payloads: fetch-and-execute one-liners,
identity-file reads, encoded blobs that decode to shell commands, config entries that spawn
processes at project open.

They exist so the detectors can be scored against labelled positives and negatives. They are
**inputs to a scanner, never something to run**.

## Rules this corpus holds itself to

- **No payload reaches a real host.** Every destination is an RFC 2606 / RFC 5737 reserved
  name or address — `*.example`, `*.example.com`, `*.example.net`, `*.test`, `192.0.2.0/24`.
  `tests/test_fixture_corpus.py` and the sweep in `scripts/dogfood.py` are what keep that true.
  A fixture that resolves in DNS is a bug, not a better fixture.
- **Nothing here executes on its own.** No fixture is imported by the test suite as code; the
  detectors read these files as *text*. Running one yourself is the only way it can act.
- **Clean twins are near misses.** Each clean case is its vulnerable twin with only the
  deciding condition removed, so a keyword grep scores badly on this corpus by design — see
  `tests/test_corpus_discriminates_mechanism.py`.

## If you are auditing this repository

Point the scanner at them rather than opening a shell in one:

```bash
node cli/bin/cli.js audit fixtures/AST01/V1-obfuscated-payload-exec --fail-on-detect
```

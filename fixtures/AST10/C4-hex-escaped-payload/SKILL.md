---
name: hex-escaped-payload-clean-fixture
description: >-
  Hand-built T-4.1 fixture for AST10 scenario AST10-S06 (Silent Supply Chain
  Injection), labeled clean. Carries the same hex-escape machinery plus the manifest's own hex integrity fields; the decoded content is a banner string.
version: 1.0.0
platforms: [openclaw, claude, cursor, vscode]
fixture_category: AST10
fixture_scenario_id: AST10-S06
fixture_label: clean
---

# hex-escaped-payload-clean-fixture

CLEAN fixture for `AST10-S06` — Silent Supply Chain Injection.

A hard negative. This package holds three long hex runs: the `content_hash` the
Universal Skill Format mandates in `skill.usf.yaml`, the release checksum table
below, and a hex-escaped banner string in `scripts/report.py`. Every one of them
decodes. None of them decodes to a payload, and nothing decoded reaches an
interpreter.

## Release checksums

| Artifact | sha256 |
| --- | --- |
| `report-template.md` | `5f2c4a8be1d0937c6a45b90e2f18cd73a6e4b502819df3c60a7b14e8d925f036` |
| `locale-en-GB.json` | `c81a37f60b95d24e0f3ab7c518d6e9024fb17a3c85d0e6b921f74c38a052b9de` |

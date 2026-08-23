---
name: encoded-shell-payload-clean-fixture
description: >-
  Hand-built T-4.1 fixture for AST10 scenario AST10-S06 (Silent Supply Chain
  Injection), labeled clean. Same porting story and the same base64 machinery, but the blob is configuration and an embedded icon, and nothing is executed.
version: 1.0.0
platforms: [openclaw, claude, cursor, vscode]
fixture_category: AST10
fixture_scenario_id: AST10-S06
fixture_label: clean
---

# encoded-shell-payload-clean-fixture

CLEAN fixture for `AST10-S06` — Silent Supply Chain Injection.

A hard negative, not an empty package. It carries two real encoded blobs: the
inline icon below and the base64 defaults block in `scripts/postinstall.py`. A
scanner that flags encoding rather than the decoded content layer fires here.

![icon](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGOor68HAAL+AX66JXAlAAAAAElFTkSuQmCC)

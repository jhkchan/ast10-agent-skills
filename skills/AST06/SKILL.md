---
name: ast06-weak-isolation
description: "Detect and triage OWASP AST06 Weak Isolation — skills executing in the host agent's security context (full filesystem, shell, and network) because sandboxing is unavailable, optional, or disabled by default, including skill-shadowing via workspace precedence and localhost WebSocket attack surface. Use when reviewing an agent runtime's default execution mode, when a workspace-level skill can override a bundled one via hot-reload, when an agent control interface binds to a network-reachable address, or when deciding whether a permission-boundary finding is AST03 or AST06."
---

# AST06 - Weak Isolation

Pattern: Knowledge. The decision rule for this category: isolation is a binary
architectural default, not a tunable policy — a runtime either sandboxes by default
or it doesn't, and "sandboxing is available if configured" is evidence *for* this
finding, not evidence against it. Mechanism (default-mode detection, bind-address
checks) lives in `scripts/`; frozen scenario tiers live in `coverage-matrix.md`.

## Why "available if configured" does not close this finding

The whitepaper's own evidence is precise on this point: OpenClaw's documentation
states "tools run on the host for the main session, so the agent has full access when
it's just you" — Docker sandboxing exists but requires explicit configuration most
users never apply. Bitdefender (Feb 2026) attributed 135,000+ internet-facing OpenClaw
instances to misconfiguration and insufficient controls, not to the *absence* of a
sandboxing feature. The decision consequence: a finding of "host-mode is the default
execution mode" is not resolved by "a sandboxed mode exists" — resolve it only by
confirming the *actual deployment* runs in the sandboxed mode, with host-mode
requiring explicit, documented opt-in.

## Decision rules

1. **Container isolation is a floor for the launched process, not a ceiling on agent
   capability.** A per-skill container constrains what the sandboxed *script* can do;
   it does not constrain what the *host agent* can be induced to do through the
   skill's natural-language output (see AST01 decision rule 2 — the two categories
   share this seam and neither closes it alone). An AST06 finding of "properly
   containerized" still leaves the induced-host-action path open; check both.
2. **Skill-shadowing exploits precedence order, not a vulnerability in any single
   skill.** OpenClaw's workspace > managed > bundled precedence means a skill planted
   in a workspace folder overrides legitimate built-in functionality — and does so
   *immediately*, via hot-reload, with no restart and (absent a control) no
   confirmation prompt. The finding is the precedence + hot-reload combination
   itself, not a defect in the shadowed skill.
3. **Bind address is a binary, high-severity signal — check it first, not last.** A
   control interface bound to `0.0.0.0` is reachable from any network peer; bound to
   `localhost`, it is reachable from any process or browser tab on the same machine.
   Neither is safe without authentication: ClawJacked (CVE-2026-32025, CVSS 7.5)
   demonstrated a loopback-bound gateway where a browser-origin WebSocket client
   bypassed origin checks and authentication throttling entirely — "localhost-bound"
   was not sufficient isolation on its own.
4. **Shared writable state across agents/sessions is a trust-boundary violation even
   with no exploit demonstrated yet.** If agent A can write to workspace, memory,
   configuration, shell, or browser state that agent B later treats as trusted with
   no re-validation, that is the finding — flag the missing provenance check, not
   only a proven cross-contamination incident. When state must be shared, the
   required control is preserving provenance and validating artifacts before
   consumption, not merely logging the share.

## Distinguishing AST06 from its neighbors

- **vs AST03 (Over-Privileged Skills):** AST03 assumes a permission model *exists*
  and asks whether a specific skill's grant is scoped too broadly for its function.
  AST06 is the absence of any isolation boundary at all — host-mode execution removes
  permission boundaries entirely, so an AST06 finding makes every AST03 manifest
  claim moot for that deployment; there is no boundary left to over-grant against.
- **vs AST01:** weak isolation is what *lets* a malicious skill (AST01) escalate a
  local finding into full host compromise — it is the amplifier, not the payload.
  Score the payload as AST01 and the missing containment as AST06 separately even
  when they co-occur in the same incident.
- **vs AST09 (No Governance):** a shadow deployment enabled by lack of isolation
  enforcement is a governance failure at the fleet level (AST09) that is *caused by*
  a technical isolation gap (AST06) at the individual-deployment level. The technical
  control (containerize by default) is AST06's fix; the fleet-visibility control
  (inventory which deployments run host-mode) is AST09's.

## Scope and out-of-artifact boundary

Whether a specific deployment's control interface actually binds to `0.0.0.0` versus
`localhost`, and whether container isolation is the enforced default versus merely
available, are runtime/configuration facts checkable against a running instance or its
deployment manifest — not always recoverable from a static skill-package artifact
alone. The static-detectable/agent-judgable split for this category (e.g., an artifact
may declare its required isolation mode without the artifact proving the *deployed*
mode matches) is fixed in `coverage-matrix.md`.

## References

Full attack-scenario catalog (Host Escape, Network Pivot, Localhost Attack Surface)
and the complete preventive-mitigation list are the whitepaper's own AST06 section
(source: `ast06.md`). This file is the delta on top of it.

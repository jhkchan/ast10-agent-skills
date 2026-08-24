---
name: ast06-weak-isolation
description: "Detect and triage OWASP AST06 Weak Isolation — skills executing in the host agent's security context (full filesystem, shell, and network) because sandboxing is unavailable, optional, or disabled by default, including skill-shadowing via workspace precedence and localhost WebSocket attack surface. Use when reviewing an agent runtime's default execution mode, when a workspace-level skill can override a bundled one via hot-reload, when an agent control interface binds to a network-reachable address, or when deciding whether a permission-boundary finding is AST03 or AST06."
---

# AST06 - Weak Isolation

Pattern: Knowledge. The decision rule for this category: isolation is a binary
architectural default, not a tunable policy — a runtime either sandboxes by default
or it doesn't, and "sandboxing is available if configured" is evidence *for* this
finding, not evidence against it. Mechanism lives in `scripts/detector.py`: the two
halves of Host Escape's defining condition — a bundled-script call site planting host
persistence, and a declared write scope reaching filesystem root — plus the declared
shell posture, shared-state write scope and sandbox declaration. Frozen scenario
tiers live in `coverage-matrix.md`.

## Orientation — read this much first

**Fires when** you are reviewing an agent runtime's default execution mode, a workspace
skill that can override a bundled one, a control interface's bind address, or a skill that
writes state another agent later trusts.

**Decides, from package bytes alone:** one scenario. `AST06-S01` Host Escape, via either
disjunct — a bundled-script call site planting host persistence, or a declared write scope
reaching filesystem root.

**Does not decide:** the other four. Bind address, workspace-over-bundled precedence,
hot-reload behaviour and cross-agent shared state are facts about a *deployment*, and no
package carries them. For those, decision rules 2–4 are the procedure and you run them by
hand against the running instance — the detector will stay silent and that silence is not
a pass.

**Freedom on this page is split unevenly between those two halves, so it is stated
rather than left to be inferred:**

| Half of the job | Freedom | Why |
| --- | --- | --- |
| **Deciding `AST06-S01`** | Low — take the disjunction as given | `scenarios/registry.yaml` states Host Escape as two disjuncts and `scripts/detector.py` implements exactly those two, the manifest side against a closed literal set of root-ish scopes. A third disjunct reasoned out mid-review is a private doctrine the corpus, the F1 and the next reviewer do not share; widening the set is an edit to the module and its fixtures, not a judgement call at review time. Where this file and `coverage-matrix.md` disagree about a tier, the matrix wins and this file is the bug. |
| **The other four scenarios** | High — no rule exists, and simulating one is the failure mode | Bind address, workspace-over-bundled precedence, hot-reload and cross-agent state are properties of an instance. Rules 2–4 tell you what to ask of that instance; what counts as an adequate answer is yours to argue. The recurring error here is not too little rigour but the wrong subject — closing on evidence about the product when the finding is about the deployment (next section). |

**Route first.** Reasoning for each cross-category call is in *Distinguishing AST06 from
its neighbors*; this table is only the jump.

| What you are holding | Go to |
| --- | --- |
| A bundled script writing a cron table, systemd unit, shell rc or launch agent | *What the two shipped checks decide* — script disjunct |
| A declared write scope of `/`, `~`, `$HOME` or `*` | Same section — manifest disjunct |
| "We ship a sandbox, it's available if you configure it" | *Why "available if configured" does not close this finding* |
| A `0.0.0.0` or loopback-bound control interface | Rule 3 — by hand, against the deployment |
| A workspace skill shadowing a bundled one via hot-reload | Rule 2 — by hand |
| Workspace, memory or browser state one agent writes and another trusts | Rule 4 — by hand |
| An honest grant that is merely too broad, boundary still intact | **AST03** — there is a boundary to over-grant against |
| The payload itself | **AST01** — isolation is the amplifier, not the payload |
| A fleet that cannot see the deployment at all | **AST09** — inventory, not containment |

**Stop after *Decision rules*** if you are producing a verdict or a remediation. Read
*What the two shipped checks decide, and where they go quiet* only when a check returned
**negative** and you must decide whether that is a pass or a blind spot.

**Layer 3 — load on condition, never by default.**

- `coverage-matrix.md` (338 lines) — **load before** re-tiering a scenario, quoting a
  coverage claim, or reporting this category's F1. **Do NOT load** it to route a finding.
- `scripts/detector.py` (526 lines) — **load before** reproducing a Host Escape false
  positive or negative, or editing the persistence-path or root-scope tables. **Do NOT
  load** it to learn what a check covers: `CHECK_COVERAGE` is reproduced per check in
  `coverage-matrix.md`, and most of what the module ships computes `artifact_signal`s for
  scenarios it does not decide — inferring coverage from the code is how that distinction
  gets lost.
- **Do NOT load either** for a deployment question. Neither file knows the bind address,
  the precedence order, or the reload behaviour of the instance in front of you.

## Why "available if configured" does not close this finding

Isolation findings get closed on the wrong evidence more often than any other category
here, and the wrong evidence always has the same shape: *a sandboxed mode exists*. It is
the wrong evidence because the population that gets compromised is the population
running the default, and the default is host mode — the agent holds full filesystem,
shell and network access, and the container is an opt-in most operators never take. The
large internet-exposure counts published for agent runtimes are attributed to
misconfiguration and absent controls, not to a missing sandboxing *feature*; the feature
was there in every one of them.

So the resolution rule is a change of subject, not a stronger argument: a finding of
"host mode is the default execution mode" is closed only by evidence about the **actual
deployment** — this instance runs sandboxed, and host mode requires a documented,
explicit opt-in. A vendor capability statement, a documentation link, and a config file
that *could* enable the sandbox are all evidence about the product, and the finding is
about the deployment. Note which one you have before you close it.

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

## What the two shipped checks decide, and where they go quiet

`AST06-S01` Host Escape is the one scenario a package decides, and the registry states
it as a disjunction, so the module implements one check per disjunct: a bundled-script
call site planting host persistence (cron table, systemd unit, shell rc, launch agent),
or a declared write scope reaching filesystem root. Both are structural facts of the
package. The module's other three checks decide no scenario and say so in their own
`CHECK_COVERAGE`: two read `artifact_signal`s, and the shell-posture check is a
`category-precondition`.

- **The script disjunct needs the persistence path as a literal string argument of a
  shell-exec or write call.** It matches `ast.Call` nodes, not text — which is why the
  module's own pattern table is not a hit against itself. A path assembled from
  fragments, read from configuration, passed through a variable, or living in a `.sh`
  file rather than a `.py` file produces no match at all.
- **An unparsed Python file is named in the evidence and still returns negative.** Treat
  the `unparsed:` note as an INCOMPLETE result; nothing downstream will do it for you.
- **The manifest disjunct compares against a closed literal set of root-ish scopes**
  (`/`, `/**`, `*`, `~`, `$HOME`, and a few spellings of each). A scope like `/etc/**` or
  `/usr/local/**` is enormously broad and is not in that set — it fires only if it also
  matches a named persistence location. Broad-but-not-root write scopes are a manual
  read.
- **Entries fully shadowed by `deny_write` are not scope and are skipped.** Correct, and
  also the shape an author uses to declare a wide `write` list that evaluates to
  nothing — which means the declaration's breadth never appears in any finding here.
- **Everything about the running system is outside the artifact.** Bind address,
  workspace-over-bundled precedence, hot-reload behaviour and cross-agent shared state
  are properties of a deployment, not of a package; four of this category's five
  scenarios are tiered out-of-artifact for exactly that reason. Decision rules 2, 3 and 4
  above are what you apply by hand, against the deployment, when this detector has
  nothing to say.

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
(source: the OWASP Agentic Skills Top 10 publication, section AST06 (no local copy: the whitepaper is not redistributable here, so this points at the publication rather than at a file in this package)). This file is the delta on top of it.

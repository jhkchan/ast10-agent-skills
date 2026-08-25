# Iteration 2 — signals

What iteration 2 measured, classified before anything acts on it. This file adds nothing to the
workspace's evidence: `benchmark.json`, `assertion-review.json`, `feedback.json` and all 88 run
directories are unmodified and stay that way. Every number below is recomputed from them and every
derivation names the file it came from.

Run under test: 44 cases × 2 arms, 0 failed, 0 excluded. Agent `bedrock/qwen3-235b`, grader
`bedrock/gpt-oss-120b`, grader blind to the arm. `feedback.json` is again empty — all 44 slugs map to
`""` — so this run, like iteration 1, has two signal sources and not three.

**Repository test baseline measured while writing this: `python3 -m pytest -q` → 2990 passed, 4
skipped in 40.89s.** The task brief states 2799 passed, 4 skipped. The measured count is 2990; the
brief's figure is stale (iteration 2's own commit added tests). Nothing here changed a test.

---

## 0. Two counts in the brief are wrong, and one of them changes the workload

| Claim | Actual | Where it comes from |
| --- | --- | --- |
| 2799 passed, 4 skipped | **2990 passed, 4 skipped** | measured, 40.89s |
| "31 of the 120 surviving assertions (26%) are failed by BOTH arms" | **41 of 120 (34.2%)** | `assertion-review.json` `buckets.failed_in_both`, filtered to non-`heldout` slugs; re-derived independently from the 88 `grading.json` files and agreeing exactly |

The bucket totals, re-derived from the raw `grading.json` pairs rather than read out of
`assertion-review.json`, and split by corpus:

| | assertions | PWFW | REG | BOTH | NEITHER |
| --- | ---: | ---: | ---: | ---: | ---: |
| tuned (33 cases) | 120 | 65 | 5 | 9 | **41** |
| held-out (11 cases) | 45 | 18 | 0 | 5 | 22 |
| **all** | **165** | **83** | **5** | **14** | **63** |

So §1 below classifies 41 assertions, not 31. The extra ten are not a rounding difference; they are a
third more work and they change the (c) share.

**The headline deltas reproduce exactly.** Case-mean tuned `with` 0.5874 / `without` 0.1424
(+0.4449); held-out 0.5091 / 0.1091 (+0.4000); gap +0.0449. Those are correct as stated.

**But the arm-level movement between iterations is the opposite of what "the skills generalised"
suggests, and it is worth stating before anything else.** Assertion-weighted, on the tuned corpus:

| | assertions | with | without | delta |
| --- | ---: | ---: | ---: | ---: |
| iteration 1 | 162 | 127 → **0.784** | 65 → 0.401 | +0.383 |
| iteration 2 (tuned) | 120 | 74 → **0.617** | 14 → 0.117 | **+0.500** |

The delta grew by 0.117. It grew because the **baseline fell by 0.284 while the skill arm fell by
0.167**. Iteration 2's assertion repair deleted 42 of 162 assertions on the same 33 cases — 23 cases
lost at least one, `AST10-case-1` and `AST01-case-2` went 5 → 2 — and what it deleted was almost
exactly iteration 1's DELETE list of baseline-satisfiable restatement. That repair worked, and it is
the single largest contributor to the measured improvement. **The skills did not get better at these
cases; the cases stopped rewarding an agent that reads a file aloud.** Any sentence of the form
"iteration 2's edits raised the delta" is unsupported by this data.

---

## 1. The 41 both-arms failures, one by one

Classification rule, stated before the verdicts, identical to iteration 1's so the two runs are
comparable:

* **(a) BROKEN** — unsatisfiable as written, or grading something the case's own request actively
  narrowed away, or requiring a fact absent from both the case's inputs and the skill. **This
  iteration I have extended (a) to cover a fourth thing iteration 1 had no name for: an assertion the
  agent satisfied and the grader recorded as failed.** Iteration 1 reported zero (a); if its grader
  erred at the rate this one does, roughly two of its 32 were mis-classified.
* **(b) TOO-HARD** — fair in principle, but demanding an enumeration, a conjunction, or a computation
  no single-pass answer of the requested shape at this agent tier can carry.
* **(c) REAL SKILL GAP** — the governing instruction is in the skill (or plainly should be), the
  case's ask is compatible with satisfying it, and the agent did not.

Every one of the 41 gets exactly one verdict. Result: **35 (c), 3 (b), 3 (a)**.

**(c) is 85.4%, against iteration 1's 81.3%. It rose, but barely — four points on a repair that
removed a quarter of the corpus.** The brief predicted a higher (c) share and it is higher, and the
size of the rise is the finding: the repair pass did not mainly convert broken assertions into fair
ones. It removed easy ones. What survived was already mostly real.

### (c) REAL SKILL GAP — 35

| Assertion | Why it is a gap, in the skill's own terms |
| --- | --- |
| `AST01-case-1` #3 | Conjunction: advise against blocking, and decline to endorse as clean. The second half is the quiet list's new "verdict and silence are one deliverable"; the first is *The predicate shape*'s "A construct with a matching declaration is **not** a finding here, however alarming it reads". Both halves are in the file; neither reached the user, who asked to be told "straight". |
| `AST01-case-2` #0 | *The predicate shape* states it verbatim — "either half alone clears". Both arms named the contradiction and neither named the negative. |
| `AST01-case-2` #1 | The weakest (c) in the set, and recorded as one deliberately. Nothing in AST01 says which operand to correct is undecidable from the artifact — but the whole predicate design says the manifest is "the *other operand*", from which it follows directly. The file states the premise and never draws the conclusion. |
| `AST01-case-3` #1 | **The skill's own NEVER works against the assertion, and that is the gap.** "NEVER put anything in `AST01-S07`'s column" reads as a prohibition on *uttering* the id; the assertion asks the agent to *name* the scenario the complaint corresponds to. Generalisable: **a prohibition on filing is read as a prohibition on naming.** The missing sentence is that the scenario is named with its tier and scored nowhere. |
| `AST02-case-2` #0 | Quote the command value at `.claude/settings.json` → `hooks.SessionStart[].command`, including the endpoint. This is iteration 1's evidence-citation defect, authorised as edit #1 and **written into only two of eleven files** (AST03's orientation, AST08's rules preamble). AST02 got a clause about naming the *limit* from the package's own files, not about quoting the *evidence*. |
| `AST02-case-2` #1 | Conjunction, half satisfied. The missed half — "the set of auto-read config paths is closed" — is quiet-list bullet 2 verbatim and a NEVER entry. |
| `AST03-case-1` #2 | The orientation's own bullet is the assertion's two examples word for word: "**Never decides** whether a grant is broad *for this skill's function*, or whether an injected instruction will later exercise it." **AST03 is one of the files that received iteration 2's "a negative is a two-part deliverable" paragraph. It did not fire here.** |
| `AST03-case-3` #3 | Quiet-list bullet 3 states the pair and the evidence each needs. Iteration 1 recorded this same assertion as (c) and named the cause — the descend table does not route a "which id do I file" question to that section. **Iteration 2 added an orientation bullet about ids and no descend-table row. Unrepaired.** |
| `AST03-case-3` #4 | `shell: false` is in the attached manifest and the fixture's own prose says the combo check must not fire. Neither arm read the field. Evidence-citation again. |
| `AST04-case-1` #1 | AST04's NEVER says it outright: the YAML check ORs two halves, "Read which half the evidence names: one fix pins `SafeLoader`, the other deletes bytes." Locating the payload in the sidecar rather than the frontmatter is that instruction applied. |
| `AST04-case-2` #0 | Decision rule 3 carries the shadowing clause verbatim. The user removed the permission block from *negotiation*, not from *explanation*, and the clause is part of how the floor was derived. Narrow, but fair. |
| `AST04-case-2` #1 | A real content gap rather than an application failure: AST04 says how the floor is derived and **never says what correcting a declared tier does and does not change**. It follows in one line from rule 3 and the file does not carry it. |
| `AST05-case-1` #0 | Quiet-list bullet 1, which the file itself calls "the highest-yield one on this whole page", and which the route table has a dedicated row pointing at. |
| `AST05-case-1` #2 | Orientation verbatim: "**Does not decide:** what a URL serves now, what it will serve at run time, or what it serves to someone else." **The identical claim WON on `AST05-heldout-case-1` #3.** Same file, same sentence, opposite outcomes — this is salience and run variance, not absent content. |
| `AST05-case-1` #3 | The AST01 seam and route-table rows 1–2, verbatim. |
| `AST05-case-2` #0 | **The most generalisable gap in the set.** The agent named the manual step and never issued the negative verdict — because AST05's orientation says a clean run "is an incomplete review, **not a negative finding**", which an agent can read as licence to withhold the negative altogether. AST08 has the counter-clause ("naming a limit … and not the verdict that hit forces reports the machinery while withholding the finding"); AST05, AST10 and AST03 do not. The `AST10-case-2` #2 regression below is the same failure. (`AST05-case-2` #1 belongs to this case too and is in (a) — the agent satisfied it and the grader missed it.) |
| `AST05-case-2` #2 | Rule 1, rule 3 and a NEVER entry all name the unverified controls, and the heldout twin won on exactly this content. **Iteration 2's AST05 orientation edit — "name every bullet that applies to the code in front of you" — was written for this and did not fire.** |
| `AST05-case-2` #3 | Orientation "Does not decide", plus *Why review-time inspection cannot close this category*. |
| `AST06-case-1` #1 | **The single most important (c) here. `AST06` decision rule 5 is an iteration-2 addition whose first sentence is this assertion** — "Planted persistence outlives the package that planted it … Uninstalling the skill … leaves that entry in place". The route table was edited in the same commit to send this exact shape to rule 5. The fixture's own docstring says it too. The fix did not land. |
| `AST06-case-2` #0 | Conjunction, half satisfied. The missed half — capability versus act — is in the NEVER ("A granted, unbounded shell is a *capability*; AST06-S01's defining condition is an *act*") and in rule 5's new closing sentence. |
| `AST07-case-1` #1 | The `sha256:` NEVER entry, verbatim. **This assertion WON in iteration 1 and lost in iteration 2 with the skill text unchanged.** With one repeat per cell and `mixed_across_repeats: 0` only because there are no repeats, the harness's noise floor is unmeasured and at least this wide. |
| `AST07-case-2` #2 | Step 3's *Insufficient* list, and iteration 2's own by-hand edit ("hand over the *Insufficient* list with it"). The agent asked for the operator-intent record and never addressed the recollection the user actually offered. |
| `AST07-case-2` #3 | *Scope and out-of-artifact boundary*, verbatim: a "single, point-in-time skill-package artifact" carries no history. The agent gave the conclusion without the reason. |
| `AST07-case-3` #2 | Routing-table row 2 plus by-hand step 1. Recorded as (c) in iteration 1, unrepaired. |
| `AST07-case-3` #3 | Conjunction whose trivial half is satisfied and whose real half — report AST07 as `declared-and-uncovered` — is missed. **Iteration 1 named this exact assertion as an authoring defect and said "split conjoined assertions into two". Iteration 2 did not split it, and separately added the AST07 orientation clause ("On a seam, something is … AST07 still owes its own row") that was written to satisfy it. Neither move landed.** |
| `AST08-case-1` #2 | Quiet-list bullet 3 (attacker-controlled declared size) and iteration 2's new "the bound has to travel with the result" paragraph. |
| `AST08-case-3` #1 | Quiet list ("deliberately excludes portability predicates") and the fixture's own prose ("only their conjunction is"). The agent reasoned correctly about C6 and dropped the separability clause. |
| `AST09-case-2` #4 | Conjunction, half satisfied. Rule 2 and its NEVER entry both enumerate the benign causes ("telemetry loss, a crashed worker, a full queue, or deletion"). |
| `AST09-case-3` #4 | **Second measured failure of a targeted iteration-2 fix.** Iteration 1 named this gap as "the agent applied rule 4 three times and never opened rule 5"; iteration 2 rewrote rule 5 to bind it to rule 4's population. The agent again applied rule 4 three times (three wins) and again never opened rule 5. |
| `AST10-case-1` #1 | The hardened form ("instead of leaving an unqualified 'safe to install' as the whole verdict") makes this fair where iteration 1's version was (b). **AST10's iteration-2 "Both, every time" paragraph is the instruction, and it did not fire.** |
| `AST10-case-2` #0 | The literal is named `ARCHIVE` in the attached file; both arms wrote "the payload". Evidence-citation, in one of the nine files that did not receive the citation clause. |
| `AST10-case-3` #3 | Precedence rule 1, verbatim: "most-specific-wins, **not first-match**". The agent gave a near-miss ("only resolves conflicts for the same path") without the named discriminator. |
| `advisory-case-1` #5 | **Third measured failure of a targeted iteration-2 fix.** Iteration 1 authorised carrying "this does not decide truth" out of the preamble and into the output contract; iteration 2 did exactly that (Phase 3 item 1: "Nothing here opened the artifact, so *routed to* is the strongest verb this file is entitled to"). The clause did not reach the answer. |
| `advisory-case-2` #3 | **Fourth.** Conjunction of a NEVER ("A ticket closed pending a scan that will never run is worse than an open ticket") and iteration 2's new Phase 3 item 4 ("the recipient is a named person and a named process rather than a file path"). The agent handed off to `skills/AST09/SKILL.md`. |
| `advisory-case-3` #4 | Same content as `advisory-case-1` #5, and worse: the with-arm actively decided truth ("the package is a clean fixture"). |

**The pattern that runs through this table, and it is the finding of §1.** Ten of the 35 are
assertions that an iteration-2 edit was written specifically to satisfy — `AST06-case-1` #1,
`AST09-case-3` #4, `advisory-case-1` #5, `advisory-case-2` #3, `AST07-case-3` #3, `AST03-case-1` #2,
`AST05-case-2` #0 and #2, `AST08-case-1` #2, `AST10-case-1` #1. Every one of those edits is present
in the shipped file, was pasted into the prompt, and is a fair reading of what the assertion asks
for. **They did not fire.** Meanwhile the held-out delta is +0.40. Both things are true, and together
they say the lift is not coming from the targeted prose. §2 says where it is coming from.

Two secondary shapes, both continuations of iteration 1:

* **Evidence-citation, 3 of 35** (`AST02-case-2` #0, `AST03-case-3` #4, `AST10-case-2` #0), plus the
  fabrication recorded in (b). Iteration 1 authorised "a stated duty to quote the artifact the conclusion is
  about" as its first edit. It was written into two files. The nine that did not get it are where
  these four sit.
* **Conjunctions authored as one assertion, 6 of 35** (`AST01-case-1` #3, `AST02-case-2` #1,
  `AST06-case-2` #0, `AST07-case-3` #3, `AST09-case-2` #4, `advisory-case-2` #3). Iteration 1 named
  this and asked for a split. Iteration 2's repair deleted 42 assertions and split none of them. A
  fix that lands one half of a conjunction still reads as no change, which means **six of the
  measurements iteration 3 will make are insensitive to exactly the improvements it will try to
  make.**

### (b) TOO-HARD — 3

| Assertion | The tension |
| --- | --- |
| `AST07-case-1` #2 | Names all three scenarios **and** states for each that a point-in-time package cannot decide it. The with-arm's verdict line already names all three and binds each to its missing evidence — that is what won #0. Requiring the additional per-scenario undecidability clause, in a case whose ask is "the verdict line I can paste", is the assertion out-scoping the case. |
| `AST08-case-2` #1 | Requires reporting the payload recovered from **the innermost of two base64 layers** of a ~300-character blob, with no tool access. That is arithmetic this agent tier cannot perform in-context, and the with-arm again substituted the skill's own illustrative `curl … \| sh` — the fabrication iteration 1 recorded, recurring **with iteration 2's example-hygiene fix in place**. The edit is right in kind and cannot succeed against a case that demands a computation the agent cannot do. The satisfiable duty is "say you did not decode it", and **no skill in the corpus tells an agent what to write when a step needs execution it cannot perform**. |
| `AST10-case-3` #2 | Demands a concrete manifest edit. The user's two-part ask is "is SOUL.md actually protected here, and what should I check instead of the warning?" — both of which the agent answered, winning #0 and #1. Borderline; listed here because the case supplies no request for a remediation. |

### (a) BROKEN — 3, and two of them are grader errors

| Assertion | What is wrong |
| --- | --- |
| `AST04-case-3` #2 | **A conditional graded as unconditional.** "*If* the output raises the breadth of the declared `shell: true` at all, it attributes that to AST03…". The grader's own evidence says the antecedent did not fire ("it only notes the shell:true declaration") and then failed the assertion. A conditional whose antecedent is false is vacuously satisfied. As written it cannot be passed by an answer that stays silent on breadth, which is the answer the case invites. |
| `AST05-case-2` #1 | **Satisfied and mis-graded.** Grader: "does not state that the clean result depends on having read the body". The response says: "yes, this version is fixed, **but only because you confirmed by hand** that `as_reference_data()` actually encapsulates the fetched content", and separately states the no-op case ("a function named `sanitize()` … that just returns the input unchanged would still clear the finding"). Both halves are present. |
| `AST07-case-1` #3 | **Satisfied and mis-graded.** Grader: "does not say any of those records decide the corresponding scenario". The response's verdict line is `could not obtain predecessor record (for Malicious Update), resolver decision record (for Rollback Attack), or reload telemetry with directory ownership (for Hot-Reload Abuse)`. The parentheticals are the binding the assertion asks for. |

Two grader false negatives in 165 assertions is ~1.2%, and both landed in the bucket that decides
what gets edited. Iteration 1's scheme had no slot for this and recorded none. **Iteration 3 needs a
fourth verdict — MIS-GRADED — or it will spend edits on behaviour the skill already produces.**

---

## 2. Where the held-out lift came from, and whether iteration 1's leanness finding replicates

### 2a. Method

Each of the 83 `passed_with_failed_without` assertions was traced from the grader's `with_skill`
evidence quote back to the passage of the relevant `SKILL.md` it restates or applies. Where a claim
is co-attributable (most are), the section supplying the *discriminating* wording — the phrasing the
agent actually reproduced — is the primary attribution. Section-class line counts use the same
classifier applied to both iterations' skill files; it reproduces iteration 1's published figures
exactly for six of seven classes (WHY-prose 237, NEVER 623, rules 680, seam 175, quiet 325, by-hand
68), so the two tables are comparable.

What iteration 2 changed in the corpus, by class:

| Class | iter 1 lines | iter 2 lines | Δ |
| --- | ---: | ---: | ---: |
| Decision rules + advisory Phases | 680 | 705 | +25 |
| Orientation + Scope | 623 | 662 | +39 |
| **NEVER lists** | **623** | **623** | **+0** |
| Quiet list / zero-detector | 325 | 343 | +18 |
| WHY-prose + predicate | 237 | 244 | +7 |
| Seam | 175 | 180 | +5 |
| By-hand procedure | 68 | 72 | +4 |
| headed total | 2765 | 2863 | +98 |

**No NEVER entry was added, removed or reworded between the two runs.** That fact is what makes the
next table interpretable.

### 2b. The yield table, and it does not replicate

| Section class | iter-2 wins | lines | share of corpus | **wins per 100 lines** | iter-1 wins/100 |
| --- | ---: | ---: | ---: | ---: | ---: |
| By-hand procedure | 5 | 72 | 2.5% | **6.94** | 2.9 |
| **WHY-prose + predicate shape** | **11** | 244 | 8.5% | **4.51** | **7.6** |
| Decision rules + advisory Phases | 27 | 705 | 24.6% | 3.83 | 2.5 |
| Quiet list / zero-detector | 9 | 343 | 12.0% | 2.62 | 2.2 |
| **NEVER lists** | **15** | **623** | **21.8%** | **2.41** | **0.8** |
| Orientation + Scope | 14 | 662 | 23.1% | 2.11 | 2.1 |
| Seam | 2 | 180 | 6.3% | 1.11 | 2.3 |

**The finding does not replicate.** Iteration 1 measured WHY-prose at 9.5× the NEVER lists (7.6
against 0.8). Iteration 2 measures 1.9× (4.51 against 2.41) over the **byte-identical** NEVER
corpus. The NEVER lists went from 5 wins to 15 with nothing changed in them. The worst-yielding class
is now the seams, not the NEVER lists.

On the held-out cases alone — the cleaner half of the data, since nothing there was tuned against —
the ordering inverts outright:

| Class | held-out wins (of 18) | lines | wins/100 lines |
| --- | ---: | ---: | ---: |
| **NEVER lists** | **6** | 623 | **0.96** |
| Decision rules + Phases | 5 | 705 | 0.71 |
| Orientation + Scope | 3 | 662 | 0.45 |
| WHY-prose + predicate | 2 | 244 | 0.82 |
| By-hand procedure | 1 | 72 | 1.39 |
| Quiet list | 1 | 343 | 0.29 |
| Seam | 0 | 180 | 0.00 |

**On unseen cases the NEVER lists carry a third of all wins — more than any other class — and
out-yield WHY-prose per line.** The six: `AST02-heldout` #0 (declines the AST02 id, quoting the
pin-posture NEVER), `AST04-heldout` #2 (the agent names *NEVER treat a parse failure as a scan*
explicitly), `AST06-heldout` #3, `AST07-heldout` #0 (the hash-pair NEVER, reproduced as a numbered
point), `AST10-heldout` #2 (`MAX_DECODE_DEPTH`, a string that appears **only** in the NEVER entry)
and `AST10-heldout` #4 (the warnings-versus-errors entry).

**What actually changed is the assertion set, not the corpus.** Iteration 2 deleted 42 assertions,
and what it deleted was the baseline-satisfiable restatement iteration 1 marked DELETE. What survived
skews hard toward *refusing to over-claim on a negative* — which is the one job a NEVER list does.
Iteration 1's yield table therefore measured **the shape of its own assertion set**, and reported it
as a property of the prose. That is the honest reading and it has one immediate consequence:

> **The leanness finding must not be used to justify deleting NEVER sections.** It was a
> single-corpus artefact, it inverts on the cleaner corpus, and acting on it would have removed the
> largest source of held-out lift in this run.

Two things about the WHY-prose class are still true and worth keeping. It remains the highest-yield
class in the corpus after the tiny by-hand sections, and it produced the run's cleanest single
attribution: **AST06's `Why "available if configured" does not close this finding` carries four of
`AST06-case-3`'s five wins** (+1.00 on that case, baseline 0/5), the same result it produced in
iteration 1. A section that wins the same case twice on two independently authored assertion sets is
the strongest evidence in this project that a passage is load-bearing.

### 2c. Which skills carried the held-out lift, and off what

Ten of eleven lifted. Attribution of the 18 held-out wins:

| Skill | held-out Δ | wins | the content that produced them |
| --- | ---: | ---: | --- |
| AST05 | **+1.00** | 4 | §3 — its own section |
| AST07 | +0.75 | 3 | the hash-pair NEVER; by-hand step 4's three-part *Sufficient* list; the orientation's one-word verdict vocabulary |
| AST03 | +0.50 | 2 | decision rules 2 and 6, both cited by number in the answer |
| AST06 | +0.50 | 2 | the orientation's two-disjunct **Decides** line; the "tightened manifest" NEVER |
| AST10 | +0.40 | 2 | two NEVER entries — decode bounds and the warnings-versus-errors validator read |
| AST01 | +0.25 | 1 | *The predicate shape*, reproduced verbatim ("One script both reads an identity artifact **and** carries an outbound send") |
| AST02 | +0.25 | 1 | the pin-posture NEVER |
| AST04 | +0.25 | 1 | the parse-failure NEVER |
| AST08 | +0.25 | 1 | *Why a clean scan result is a claim about coverage* — PASS/FAIL/INCOMPLETE |
| AST09 | +0.25 | 1 | decision rule 6, cited by number |
| advisory | **0.00** | 0 | §2d |

### 2d. advisory's held-out failure is not a missing scope gate

The brief says advisory "has no SCOPE GATE: every finding gets a category because the skill assumes
the finding is in scope." **That is not what the file says.** `skills/advisory/SKILL.md` carries the
gate twice, and both statements are exactly on point:

* *When this is the wrong entry point*, row 3: "A finding about an **MCP server**, a bare tool, or a
  host plugin | Out of scope. AST01-AST10 apply to the skill form specifically - the whitepaper draws
  that boundary itself … and MCP servers belong to the MCP Top 10. **Return null.**"
* NEVER, last entry: "**NEVER invent an AST id for something that is not a skill.** An MCP server, a
  bare tool, or a host plugin is outside AST01-AST10 by the whitepaper's own scope split. `triage()`
  returns null for unmatched text; the null is the answer."

And iteration 2 added, immediately under that table: "**The rows above are terminal.** Name the entry
point and stop - no origin, no contributing list, no hand-off record, no `ast_id`."

The finding text contains the literal words "MCP server". The agent emitted `ast_id: AST06`, recorded
AST08 and AST09 as contributing, and handed off to `skills/AST06/SKILL.md`.

**So the defect is precedence, not absence.** The scope check lives in an aside headed *When this is
the wrong entry point*, before the procedure; the procedure itself begins at Phase 1, whose table has
a row ("No boundary existed to contain whatever ran → AST06") that fits the finding's surface
perfectly. An agent executing the file runs Phase 1. Nothing in Phase 1 asks the scope question, and
nothing sequences the aside ahead of it. Stated as behaviour rather than as a case: **a gate that is
not a step in the procedure is not a gate.** That generalises past MCP servers to every prompt where
the correct output is a refusal and the routing table has a plausible row.

The same shape is visible in three other (c)s — `AST01-case-3` #1, `AST03-case-3` #3, `AST07-case-3`
#2 — where the governing content sits in a section the descend table does not route the question to.

---

## 3. AST05's +1.00, and the shape worth borrowing

`AST05-heldout-case-1` is 4/4 with the skill against 0/4 without, the largest single lift measured
anywhere in this project. The two answers are worth putting side by side, because the flip is total:

> **baseline:** "Yes, you can record AST05 as passed for this package. … There are no gaps in
> coverage; the check passes and fully satisfies the requirements."
>
> **with skill:** "You **cannot** record AST05 as passed for this package based solely on a clean
> dataflow check."

### What the skill caused the agent to do, assertion by assertion

| Assertion | The skill content the answer reproduces |
| --- | --- |
| #0 — no instruction-sink finding, and parsing a fetched body as data is *correct handling*, not a suppressed finding | quiet list: "**`json.loads(response.text)` is not a sink and must not be made one.** Parsing a body as data is the correct handling" |
| #1 — declines to record AST05 as passed *at scenario level*, because every shipped check is an enabling-precondition proxy | orientation: "**Decides:** nothing at scenario level … this category publishes no scenario-level F1". The agent cites the source: "as stated in the skill's orientation" |
| #2 — nothing verified a content-hash pin re-checked before ingestion | decision rule 1, quoted verbatim by the agent as a block quote |
| #3 — what the host serves at run time is not observable; a reviewer's fetch is not evidence about a live agent run | decision rule 3, whose own "The decision consequence:" clause is the assertion |

### The shape, named

Three components, and all three are needed:

1. **The `Decides` line is itself a refusal, stated in the vocabulary the answer must use.** AST05
   does not say "decides one scenario"; it says "**nothing at scenario level**", and pairs it with an
   explicit `Does not decide:` line. The agent's default frame becomes *this cannot be closed*
   rather than *let me check whether it can be closed*. Compare the baseline, which had no frame and
   defaulted to the user's.
2. **The decision rules are named controls a reviewer can look for the absence of** — a hash pin
   re-verified on every load, a redirect policy, bait-and-switch resistance, bounded
   reference-following, chain minimum-resistance, snapshot-over-fetch — and **each carries an
   explicit consequence-for-the-verdict clause** ("The decision consequence: a scan result is
   evidence about what the scanner's fetch saw, not evidence about what any given agent's fetch will
   see"). This is why the agent could produce the deliverable the assertions want: *what this clean
   result did not verify* is enumerable straight off the rule list, one line at a time.
3. **One sentence binds the verdict and its bounds into a single deliverable** — "A clean run of the
   five checks with no manual step beside it is an incomplete review".

The agent's answer inherits AST05's own two-column freedom table as its structure: *What the dataflow
check did confirm* / *What the checks do not cover*. That is the shape, reproduced.

### It already generalises inside this corpus

The three skills whose orientation states a refusal — AST05 ("nothing at scenario level"), AST07
("does not decide any named scenario … verdict vocabulary is one word"), AST09 ("**Decides nothing
from the package**") — plus advisory ("**Does not decide** whether the finding is true") carry **40
of the 83 wins on 4 of 11 skills**. Add AST06, whose WHY-prose is a refusal argument, and it is 50 of
83. This is not eleven skills performing evenly; it is a shape performing.

### What the other ten are missing, in one sentence

Component (1) is cheap and six files have some version of it. Component (2) is the one that
distinguishes AST05, AST09 and AST07 from AST01, AST04 and AST10: **their rules are classification
tests, and a classification test cannot be run backwards.** "Is this a two-part predicate?" yields no
list of things a negative failed to establish; "is the pin re-verified on every load?" yields one
directly. The borrowable move is not to rewrite the tests — it is to give each rule the clause
AST05's rule 3 has, naming what a negative on that rule does not establish. That is WHY-shaped, it is
one line per rule, and it is the same duty §1 shows nine files not discharging.

---

## 4. Cost — 7.0×, and whether it buys work or recitation

Recomputed from all 88 `timing.json` files:

| | input tok | output tok | total | response chars | prompt chars |
| --- | ---: | ---: | ---: | ---: | ---: |
| `with_skill` mean | 5468 | 486 | 5954 | 2178 | 23085 |
| `without_skill` mean | 594 | 255 | 849 | 1234 | 2305 |
| delta | **+4874** | **+231** | +5105 | +945 | +20780 |

**95.5% of the token delta is input** — the `SKILL.md` pasted into the prompt, ~20 800 extra prompt
characters per run. The agent's own production rises by 231 tokens, about 90%. The honest cost
statement is unchanged from iteration 1: *the skill costs ~4 900 tokens of context to hold and ~230
tokens of extra answer to use.* 5 105 extra tokens per run × 44 runs bought 83 wins − 5 regressions =
**78 net flips, ~2 880 extra tokens per assertion gained** (iteration 1: ~2 600).

### Per skill: is the extra output work?

| Skill | with/tot | without/tot | WIN | REG | Δchars | Δchars/win | Δtok/win |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| AST09 | 14/19 | 0/19 | 14 | 0 | 6290 | 449 | **1 379** |
| AST06 | 10/15 | 1/15 | 10 | 1 | 3798 | 380 | 2 009 |
| AST07 | 10/18 | 0/18 | 10 | 0 | 3770 | 377 | 2 009 |
| AST08 | 10/16 | 3/16 | 8 | 1 | 2459 | **307** | 2 043 |
| advisory | 12/19 | 1/19 | 11 | 0 | 3811 | 346 | 2 189 |
| AST10 | 7/14 | 2/14 | 6 | 1 | 3424 | 571 | 3 076 |
| AST03 | 10/14 | 4/14 | 6 | 0 | 2999 | 500 | 3 151 |
| AST01 | 9/15 | 3/15 | 6 | 0 | 3287 | 548 | 4 176 |
| AST02 | 5/10 | 0/10 | 5 | 0 | 3002 | 600 | 4 206 |
| AST05 | 7/14 | 2/14 | 5 | 0 | 6193 | **1 239** | 4 206 |
| **AST04** | **3/11** | **3/11** | **2** | **2** | 2536 | **1 268** | **10 112** |
| ALL | 97/165 | 19/165 | 83 | 5 | 41 569 | 501 | 2 706 |

**Substantively the extra output is work, not recitation, for nine of eleven skills.** The two
exceptions are named:

* **AST04 is the skill whose output is closest to paying for nothing.** Two wins against two
  regressions, net zero on the arm-level score (3/11 both arms), 10 112 extra tokens per win — five
  times the corpus median. Both regressions are on `AST04-case-3`, and both are the with-arm
  producing a *worse-scoped* answer than the baseline: it wrote "**All AST04 checks pass**" where the
  baseline wrote "`APPROVED - AST04-S4 satisfied: observed network egress aligns with declared
  allowlist`". The skill turned a scoped clearance into a blanket one.
* **AST05 buys its five wins at 1 239 chars each and carries the clearest single instance of paid-for
  recitation in the run.** `AST05-case-3` scores 2/2 in *both* arms; the with-arm is 3 691 characters
  against the baseline's 1 938 and carries eight skill-machinery mentions. 1 750 extra characters and
  4 300 extra tokens for zero graded gain. It also closes on a misattributed citation — *"Rule 2 in
  Where the shipped checks go quiet says: 'NEVER accept a boundary you have not read'"* — which is a
  NEVER entry, is not in the quiet list, and is not numbered.

### Three symptoms worth recording, one of them serious

1. **Register, worse than iteration 1.** Skill-internal machinery (NEVER, "decision rule N", quiet
   list, freedom table, `CHECK_COVERAGE`, `declared-and-uncovered`, MANDATORY) surfaces in **35 of 44
   `with_skill` responses, 98 mentions, mean 2.2**, against 14 of 44 baseline responses and 20
   mentions. Iteration 1 measured 21 of 33 at mean 1.8. The agent is quoting the skill's directive
   apparatus at a colleague more often, not less.
2. **Citation fabrication.** `AST10-heldout-case-1` cites "**rule 9**" as governing and paraphrases a
   NEVER entry it invents wording for; AST10's decision rules are numbered 6, 7, 8, and its rule 9
   lives in a different section. `AST05-case-3` misattributes as above. These are cheap to dismiss
   as style, and they are the same mechanism as (3).
3. **A fabricated scenario id passed a graded assertion.** `AST02-heldout-case-1` correctly declines
   `AST02-S02` — and substitutes **`AST08-M01` "(Misconfigured or Missing Dependency Pinning)"**, an
   identifier that appears nowhere in this repository outside the eval outputs. The assertion asked
   the agent to decline an AST02 id and not substitute *another AST02 id*; it did exactly that, and
   scored a WIN. The skills teach a refusal-to-over-claim discipline about ids and **not one of them
   says an id you cannot cite from the registry is not an id.** The assertion cannot catch this
   because it constrains the prefix rather than the existence of the id.

### The nine cases that discriminate nothing

`AST01-case-2`, `AST02-case-2`, `AST03-case-1`, `AST04-case-2`, `AST05-case-2`, `AST05-case-3`,
`AST06-case-1`, `AST10-case-2`, `advisory-heldout-case-1` score identically in both arms — 9 of 44
cases, 18 model calls per iteration, zero information. Five of them score 0/n in both arms, which is
a different problem from `AST05-case-3`'s 2/2: a case both arms fail completely is measuring
something no arm reaches, and `advisory-heldout-case-1` is the extreme (with-arm 1 502 characters and
0/4; baseline 5 characters — the single word "AST03" — and also 0/4).

---

## 5. What this file authorises, and what it does not

**Authorised as skill edits — each justified by underlying behaviour, stated in the skill's own
terms, expected to help on prompts nobody has written, and deliberately fewer than the gap count:**

1. **Make the scope question a step in the procedure, not an aside before it** (advisory Phase 1;
   the descend tables in AST01, AST03, AST07). Justification: §2d, plus three (c)s where the
   governing content sits in a section the routing table never sends the question to. A gate that is
   not a step is not a gate.
2. **Give each decision rule the clause AST05's rule 3 has — what a negative on this rule does not
   establish.** Justification: §3. This is the mechanism behind the largest measured lift in the
   project, it is WHY-shaped, it is one line per rule, and it is what nine files were missing when
   iteration 2's "report the negative with its bound" paragraphs failed to fire (§1).
3. **Add the withheld-verdict counter-clause where only AST08 has it** (AST05, AST10, AST03).
   Justification: `AST05-case-2` #0 and the `AST10-case-2` #2 regression are the same failure — the
   "a negative is not a result on its own" doctrine suppressing the negative entirely. AST08 already
   carries the sentence; three files need it and none needs a new section.
4. **Finish iteration 1's evidence-citation duty in the nine files that did not get it.**
   Justification: four (c)s and one fabrication. It was authorised, it was written into two files,
   and the failures are all in the other nine.
5. **Say that an identifier you cannot cite from the registry is not an identifier.** Justification:
   §4 symptom 3 — a fabricated id earned a graded pass, and the corpus's entire id discipline is
   about which id, never about whether the id exists.

**Explicitly NOT authorised, and recorded so nobody acts on the earlier finding:**

* **Do not trim or delete NEVER sections on the strength of iteration 1's yield table.** §2b: the
  table does not replicate over a byte-identical corpus, and on held-out cases the NEVER lists are
  the *highest*-yielding class. Iteration 1 measured its own assertion set.
* Do not add a rule per failed assertion. Iteration 2 added ten targeted passages for ten named gaps
  and §1 shows all ten still failing. More prose aimed at named assertions is the move that has now
  been measured twice and worked neither time.
* Nothing here justifies naming, numbering or paraphrasing an eval case inside a `SKILL.md`. Every
  proposal above is stated as a behaviour; case slugs appear only in this analysis file.

**Repairs that belong to the eval, not to any skill:**

* Split the six conjunctions in §1 into two assertions each — never into one weakened one.
* Fix the vacuous conditional (`AST04-case-3` #2) and re-grade the two mis-graded assertions.
* Add a **MIS-GRADED** verdict to the classification scheme; a 1.2% grader false-negative rate lands
  entirely in the bucket that drives edits.
* Rebuild or retire the nine zero-discrimination cases (§4).
* **Repeat cells.** `mixed_across_repeats: 0` is reported as a noise floor and is an artefact of one
  repeat per configuration. `AST07-case-1` #1 won in iteration 1 and lost in iteration 2 against
  unchanged skill text; the harness's real noise floor is unmeasured and at least that wide, and
  every per-skill held-out delta in this run rests on four assertions in one cell.
* The fixture self-label contaminant iteration 1 recorded (§7 there) is still present in the
  attached files and is still a harness repair.

**Corpus status.** `skills/*/evals/heldout.json` is retired to `regression.json` and this file calls
it a regression corpus throughout; iteration 3's control is being authored separately and no
`control.json` was read or written while producing this analysis. No gate constant, no scorecard, no
iteration-1 or iteration-2 evidence file is implicated by anything above. This file is the only
addition to `iteration-2/`.

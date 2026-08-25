File this under **AST03 — Over-Privileged Skills** as the origin. The scanner missing it is a contributing control failure, not the root cause.

Here’s why:

- **Origin:** The skill was granted write access to production secrets. For this to matter, the grant itself had to already be overly broad — that’s **AST03**, because the excessive privilege is what *enabled* the risk. This is a preventable condition: had the grant been least-privilege, the finding wouldn’t exist.
  
- **Contributing failure:** The scanner didn’t flag it — that’s **AST08**, but only as a *catcher*, not the *preventer*. AST08 is contributing here because scanning is a detection mechanism, not a prevention one. The fix owner for AST08 is whoever operates the scanner; the fix owner for AST03 is the skill author or registry.

- **Misrouting risk:** Your instinct to pick AST08 is common, but it reflects the loudest symptom (the missed detection), not the origin. The shipped routing script often gets this wrong too — it prioritizes AST08 due to phrase order — but **Phase 2 of advisory corrects it** using the *preventer vs. catcher* test.

- **Hand-off:** Route to `skills/AST03/SKILL.md`.  
  The check there can return *one scenario-level verdict* (on Identity File Backdoors), plus static signals. But this finding is about excessive runtime privilege — a core AST03 scenario — so the hand-off can meaningfully assess it.

Also note: **AST08 cannot be the origin here** unless the artifact under review *is the scanner itself*. Since the finding is about a skill’s privileges, AST08 only contributes.

Final record:  
- `ast_id: AST03`  
- Contributing: `AST08` (owned by scanner operator; action: improve detection coverage)  
- Hand off to: `skills/AST03/SKILL.md`  
- What the target can confirm: One of five scenario verdicts (Identity File Backdoors), plus judgment on whether this grant is excessive. Other checks in AST03 are artifact signals, not scenario-level confirmations.

Don’t let the scanner’s silence distract from the real issue: the privilege was too wide to begin with.
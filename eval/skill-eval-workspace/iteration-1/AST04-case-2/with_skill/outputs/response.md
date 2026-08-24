The package declares `risk_tier: L0`, which asserts it operates at the lowest risk level (read-only, no identity-altering writes, no egress, no shell). However, the permission block grants `shell: true` and an effective write capability to `reports/summary.md`. According to the derived risk floor logic in `validators/usf.py`, any manifest with shell access combined with write permissions — even when narrowly scoped — must be classified at **L3**, the highest risk tier.

This creates a metadata contradiction: the declared `risk_tier` (L0) is strictly **below** the derived permission floor (L3), constituting **AST04-S03: Risk Tier Spoofing**.

**Contradiction:** `risk_tier: L0` declared despite shell + write permissions requiring L3.  
**Fix:** Change `risk_tier: L0` to `risk_tier: L3` to align the declared risk level with the permission-derived floor.
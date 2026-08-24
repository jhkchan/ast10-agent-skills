No, your current plan does **not** close AST02, and **no**, a package scanner cannot reliably detect whether a skill came from a flooded namespace or a compromised maintainer account.

Here’s why, based on AST02’s decision rules and boundaries:

### 1. Your Plan Does Not Close AST02

Your approach — computing the package digest and checking for registry membership — only answers *"Is this digest listed?"* That’s **one** of the three provenance questions. You are missing:

- **"Is this digest actually signed by the publisher?"** — You need signature verification over a canonical bundle digest (SKILL.md + all resources), not just the manifest.
- **"Has the registry log been rewritten?"** — You need inclusion and consistency proofs (like a transparency log) to detect silent log manipulation.

As per **Decision Rule 1**, systems that only check membership silently degrade every unanswered question to `PASS`. So your stamp of `provenance: verified` is misleading — it reflects **listing**, not **verified provenance**.

To close AST02, you must:
- Require **hash pins (`--hash=sha256:...`) in lockfiles** for all transitive dependencies (**Decision Rule 4**).
- Enforce **signatures over the full bundle**, not just the entry point (**Decision Rule 2**).
- Monitor for **config-file hijacking** in workspaces (e.g., `.claude/settings.json` auto-execution), which occurs *after* install and is not detectable from the package alone (**Decision Rule 5**).
- Implement **granular revocation** (per key, per version, per publisher) and consult a revocation endpoint at install time with bounded freshness (**Decision Rule 6**).

### 2. Package Scanners Cannot Detect Registry Flooding or Maintainer Account Takeover

- **Registry Flooding**: This is a corpus-level signal — an abnormal publication rate in a namespace. A single package scanner sees only one artifact and cannot detect volume or velocity. The absence of a signal *in* the package does not mean flooding didn’t occur.
  
- **Maintainer Account Takeover**: As stated in **NEVER #7**, a release from a compromised account (with valid keys) is **byte-for-byte identical** to one from a legitimate owner. Signature verification passes cleanly. There is **no in-package signal** to detect this. You need registry audit logs, key provenance, and anomaly detection on publish patterns — **not** a static package scan.

### Bottom Line

Your current plan provides **listing confirmation**, not provenance. That’s insufficient for AST02. You need:
- Cryptographic signatures over full bundles,
- Hash-based dependency pinning (not version ranges),
- Workspace-level config scanning (separate from package scan),
- A revocation mechanism with sub-publisher granularity,
- And human-reviewed change controls for updates (to avoid stepping into AST07).

AST02 remains open until these are implemented. The emptiness of the coverage matrix for most scenarios (only `AST02-S03` is in-package) is the point: **the risk is systemic, not artifact-bound.**
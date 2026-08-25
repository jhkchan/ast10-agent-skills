No, your plan does not close AST02, and no, a package scanner cannot determine whether a skill came from a flooded namespace or a compromised maintainer account.

Here’s why:

Your current approach — verifying that a package digest appears in the registry index — only answers one of the three critical provenance questions: *Is this digest listed?* But AST02 requires answering two additional questions that your mechanism does not address:

1. **Was this digest actually signed by the legitimate publisher?**  
   Your lookup doesn’t verify a cryptographic signature over the package content tied to a resolvable publisher identity. Without that, an attacker who gains upload privileges (via account takeover) can publish malicious packages that still "match" the index.

2. **Has the registry’s history been rewritten to hide the attack?**  
   Your method assumes the index is honest and immutable. Without transparency logs with inclusion and consistency proofs (e.g., Merkle trees monitored by stakeholders), a malicious registry operator or compromised backend could silently replace entries.

So while your system checks *listing*, it conflates “found” with “verified,” which AST02’s decision rule #1 explicitly warns against. That conflation is the failure mode: it produces a false pass on provenance when only the weakest control is in place.

Regarding detection via scanning:

- **Registry flooding** and **maintainer account takeover** are out-of-artifact scenarios — they depend on observing publication patterns, account access logs, and resolver behavior over time, not on analyzing package contents.
- A single package, once released, carries no in-artifact signal that it was part of a flood or published by an attacker using stolen credentials. If the attacker signs with the legitimate key (as in a true account takeover), the artifact is *byte-for-byte identical* to a legitimate one.

Therefore, no static scanner analyzing individual packages can detect these conditions. Detection requires auditing registry-wide signals: authentication logs, key rotation events, publication velocity, DNS/URL anomalies, and resolver resolution logic (e.g., whether private package names collide with public ones, enabling dependency confusion).

In short:  
✅ You’ve implemented *discovery*.  
❌ You have not implemented *provenance*.

To close AST02, you must add:
- Cryptographic signatures over canonical package bundles (decision rule #2),
- A revocation mechanism with per-version and per-key granularity (rule #6),
- And transparency mechanisms (like a verifiable log) to detect index tampering (rule #1).

And again: **no package scanner can rule in or out a maintainer account takeover or namespace flood from artifact contents alone.** Those are corpus- and process-level audits, not code-level checks.
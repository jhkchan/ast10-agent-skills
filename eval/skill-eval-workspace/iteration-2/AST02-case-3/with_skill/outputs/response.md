No, your current install-time plan does **not** close AST02, and a package scanner **cannot** determine whether a skill came from a flooded namespace or a compromised maintainer account — not from the artifact alone.

Here’s why:

Your plan performs only one of the three distinct provenance checks that AST02 requires:
1. **"Is this package listed?"** — Yes, you do this via digest lookup.
2. **"Is this the digest the publisher actually signed?"** — No. You are not verifying a signature over a canonical bundle (SKILL.md + all declared files). Without that, an attacker could publish a malicious package with a valid digest that was never signed by the legitimate publisher.
3. **"Has the registry log been rewritten?"** — No. You lack inclusion and consistency proofs (e.g., a verifiable log like a transparency log) to detect if the registry was tampered with after the fact.

Answering only the first question creates a silent failure: the result looks the same whether full provenance controls are in place or only the weakest one. That’s a core AST02 anti-pattern.

Second, **neither registry flooding nor maintainer account takeover can be detected by inspecting a single package**. These are corpus-level events:
- **Registry flooding** is a rate-of-publication anomaly. You’d need to monitor publish velocity across namespaces over time — no single package carries that signal.
- **Maintainer account takeover** produces packages that are cryptographically indistinguishable from legitimate ones if the attacker holds the signing key. A scanner seeing only the package content cannot rule this out. The evidence lives off-artifact: in auth logs, key provisioning trails, and publication patterns.

A clean scan result does **not** mean "no compromise occurred" — it means "no in-package signal was found," which is not the same thing.

To close the AST02 gap:
- Sign **the entire bundle**, not just metadata, and verify that signature using a key you trust through a secure channel.
- Use **hash pins** in lockfiles, not version ranges, and enforce them **transitively** for all dependencies.
- Monitor **publication patterns** and **signing key provenance** independently.
- Consult a **revocation endpoint** at install time, valid for a bounded window, with support for granular revocation (key, package version, publisher).

And critically: **do not treat registry membership as a security signal**. “Found” does not equal “verified.”
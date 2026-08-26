---
name: validate-usf-manifest
description: >-
  Validate a Universal Skill Format v1.0 manifest (skill.usf.yaml) against both halves of the
  contract - the JSON Schema that constrains its shape and the semantic rules a schema cannot
  express (deny_write precedence, default-deny network evaluation, identity-file protection,
  derived risk_tier floor, JCS signing payload, content_hash agreement) - or emit a
  schema-valid starter manifest for a package that has none.
nl_triggers:
  - "validate this USF manifest"
  - "check my skill.usf.yaml"
  - "is this manifest schema valid"
  - "generate a universal skill format manifest"
  - "emit a USF manifest for this skill"
  - "why is my risk_tier rejected"
  - "deny_write precedence"
  - "does the content hash match the package"
  - "what should the signature field say"
  - "wildcard domain in the network allowlist"
routes_to: ast10-cross-platform-reuse
---

# /owasp-ast10:validate-usf-manifest

Activates the `ast10-cross-platform-reuse` skill (`skills/AST10/`) and runs
`validators/usf.py` over one or more manifests. USF is the whitepaper's own proposed
cross-platform manifest standard — the mitigation for AST10, and the metadata foundation the
other nine categories read from. This command is the executable half of that proposal.

## The two halves, and why a schema alone is not enough

`schemas/usf-v1.schema.json` constrains the manifest's **shape**: required fields, semver,
the `sha256:<64 hex>` form of `content_hash`, the `unsigned`-or-ed25519 `signature`, the
`L0..L3` `risk_tier` enum. `validators/usf.py` constrains its **semantics** — the rules JSON
Schema structurally cannot state:

| Rule | What it enforces |
| --- | --- |
| Network is default-deny | Only hosts in `network.allow` may be reached, so `deny: "*"` is *redundant with* — never an override of — that default. Any other `deny` value is rejected, because it implies the author believes `deny` is a precedence list. |
| `deny_write` wins over `write` | For any path both lists name, the deny wins. Not a merge, not last-wins. |
| Explicit paths only | No wildcards in `permissions.files`. A `..` segment is rejected too: an explicit path that can escape its root is not explicit. |
| Identity files protected by default | `SOUL.md`, `MEMORY.md`, `AGENTS.md` must each appear in `deny_write` unless explicitly granted in `write`. Omission is an error, not a default. |
| Host-only network matching | `*.example.com` is rejected — the matcher is host-only, so a wildcard subdomain would never match and reads as broader access than is actually granted. |
| `risk_tier` is an untrusted assertion | A floor is derived from the declared permission set; under-declaration is rejected. That under-declaration is exactly the AST04 risk_tier-spoofing shape. |
| `content_hash` must agree | Recomputed over the package surface. A mismatch means the signature would cover a package that is not the one shipped. |
| Signing payload is RFC 8785 (JCS) | Canonical JSON excluding `signature`, including `content_hash`. |

Two additional strictness rules are this repo's own and say so in their own error text: the
`..` rejection above, and `scan_status.scanner`/`result` having to agree about whether a scan
actually happened.

## Arguments

| Position | Argument | Required | Meaning |
| --- | --- | --- | --- |
| `$1…` | `<manifest-path>…` | yes, unless `--emit` | One or more `skill.usf.yaml` paths. Multiple paths are validated in one pass and each gets its own verdict line. |
| `$2…` | `--strict` | no | Treat warnings as failures. Without it, warnings print and the verdict still passes. |
| `$2…` | `--update-content-hash` | no | Recompute `content_hash` from the manifest's own skill directory and rewrite it in place before validating. |
| `$1` | `--emit <package-path>` | no | Package has no manifest: scaffold a schema-valid starter from the package's actual contents, then validate it. Mutually exclusive with passing manifest paths. |

`--emit` never invents a permission. It writes the three `files` lists (all required even
when empty), an empty `network.allow` with `deny: "*"`, `shell: false`, `signature:
unsigned`, and the derived `risk_tier` floor — then leaves every widening decision to a
human, because a generated manifest that guesses generously is the AST10 implicit-privilege-
escalation shape in a new coat.

## Example invocation

```text
/owasp-ast10:validate-usf-manifest ./invoice-helper/skill.usf.yaml
```

Equivalent deterministic run:

```bash
python3 validators/usf.py ./invoice-helper/skill.usf.yaml
```

The manifest below declares `platforms: [claude, cursor]`, `risk_tier: L0`, an empty
`deny_write`, `network.allow: ["*.example.com"]`, `shell: true`, and a placeholder
`content_hash`.

## Output

```text
skill.usf.yaml: ERROR: permissions.files.deny_write: identity file SOUL.md is neither denied nor explicitly granted in write; USF v1.0 protects identity files by default and requires an explicit override
skill.usf.yaml: ERROR: permissions.files.deny_write: identity file MEMORY.md is neither denied nor explicitly granted in write; USF v1.0 protects identity files by default and requires an explicit override
skill.usf.yaml: ERROR: permissions.files.deny_write: identity file AGENTS.md is neither denied nor explicitly granted in write; USF v1.0 protects identity files by default and requires an explicit override
skill.usf.yaml: ERROR: permissions.network.allow: '*.example.com' uses a wildcard; USF v1.0 matching is host-only, so a wildcard subdomain would never match and reads as broader access than is actually granted
skill.usf.yaml: ERROR: risk_tier: declared L0 is below the L3 floor derived from the declared permissions. risk_tier is an untrusted author assertion and MUST be validated against the permission manifest; under-declaration is the AST04 risk_tier-spoofing shape
skill.usf.yaml: ERROR: content_hash: manifest declares sha256:0000...0000 but the package surface at . hashes to sha256:e3b0c442...7852b855; the signature would cover a package that is not the one shipped
skill.usf.yaml: warn: author.identity: no decentralized identity anchor declared; a registry cannot bind this package to a publisher, so installation counts and author names remain unverifiable trust signals
skill.usf.yaml: warn: scan_status is absent; a consumer cannot distinguish 'never scanned' from 'scan metadata lost in a port'. Declare result: unscanned instead of omitting the field
skill.usf.yaml: FAIL (signature=unsigned, risk_tier floor=L3, 6 error(s), 2 warning(s))
```

Exit code is 1 when any manifest fails, 0 otherwise. A passing manifest prints only its
verdict line and any warnings:

```text
skills/AST01/skill.usf.yaml: OK (signature=signed, risk_tier floor=L0, 0 error(s), 0 warning(s))
```

### Reading the verdict line

- `signature=` reports one of three **states**, and only one of them is a defect.
  `signed` means the field holds a well-formed `ed25519:<128 hex>` value — the validator
  reports the shape, and checking it against a published key is
  `python3 scripts/sign_usf.py verify --identity did:web:<domain>`. `unsigned` is the
  explicit, auditable declaration that the package ships without one — far better than a
  signature field that anchors to nothing, which manufactures the false trust signal AST10
  warns about — and whether that is acceptable is the consumer's policy call. `malformed`
  is the defect: neither a real signature nor an honest placeholder.
- **A signature answers "who published this", never "is this safe."** A `signed` verdict
  line, and even a `verify` that passes against a live anchor, says nothing about
  `scan_status`, about review, or about what the package does when it runs.
- `risk_tier floor=` is the tier **derived from the permissions**, not the tier the author
  wrote. When the two disagree downward, that is an error above; when they agree, the
  author's claim has been independently confirmed rather than believed.

## Related

- `/owasp-ast10:audit-ast10` — the category this manifest standard mitigates, and the reason its
  detector ships zero functions: the work lives in the validator, not in a detector.
- `/owasp-ast10:audit-ast04` — a manifest that parses cleanly can still lie. Metadata deception and
  unsafe frontmatter deserialization are AST04's surface, not USF's.
- `/owasp-ast10:audit-skill-package` — runs this validator as its first step whenever the candidate
  package carries a `skill.usf.yaml`.
- `schemas/usf-v1.schema.json` and `validators/usf.py` — the shape half and the semantic
  half. Where they disagree, the validator's error text names which rule it is applying.

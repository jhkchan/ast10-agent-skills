# Signing the USF manifests

All eleven manifests ship `signature: "unsigned"` today, and `author.identity` and
`author.signing_key` are **absent rather than empty**. That is a decision, not a to-do:
publishing a DID or a public key that anchors to nothing manufactures exactly the false
trust signal AST10 warns about. This page is the runbook for the day that changes — and
for the day, months later, when you have to re-sign, rotate, or explain what the signature
is worth.

Everything below is done by `scripts/sign_usf.py`. Two properties of that tool shape the
whole procedure:

- **Signing and anchoring are one operation.** `sign` writes `author.identity`,
  `author.signing_key` and `signature` in a single rewrite, and all three are *inside* the
  signed payload. There is no code path that produces a signature without an identity, and
  a signature cannot be moved to a different identity without breaking verification.
- **The private key never enters this repository and never enters CI.** `keygen` and `sign`
  refuse to run when the environment says CI; `keygen` refuses to write a key anywhere
  inside the working tree. See [The key is never in CI](#the-key-is-never-in-ci).

Contents: [Before you start](#before-you-start) · [The four commands](#the-four-commands) ·
[When you must re-sign](#when-you-must-re-sign) · [What a signature proves](#what-a-verified-signature-proves-and-what-it-does-not) ·
[Key loss and rotation](#key-loss-and-key-rotation) · [The key is never in CI](#the-key-is-never-in-ci) ·
[After the first signing run](#after-the-first-signing-run)

---

## Before you start

You need three things, and the first one is the one that actually matters:

1. **A domain you control**, served over HTTPS with a certificate valid for that domain.
   The trust anchor is `did:web`, the USF specification's own example form, and a
   `did:web` anchor is worth exactly as much as your control of the domain and its TLS.
2. **A place to keep the private key that is neither this repository nor CI.** The default
   is `~/.config/ast10-signing/ed25519.pem` (directory `0700`, key `0600`).
3. **`cryptography` installed** (`pip install cryptography`). `validators/usf.py` imports it
   lazily; the signer needs it outright.

Do this on the machine that holds the key, at release time, and nowhere else.

---

## The four commands

```bash
python3 scripts/sign_usf.py keygen
python3 scripts/sign_usf.py did-doc --identity did:web:YOUR.DOMAIN --output did.json
#   ... publish did.json, then:
python3 scripts/sign_usf.py sign   --identity did:web:YOUR.DOMAIN
python3 scripts/sign_usf.py verify --identity did:web:YOUR.DOMAIN
```

Replace `YOUR.DOMAIN` with the domain from step 1 every time it appears. The identity is a
runtime argument, never a constant in this repository: nothing here hardcodes a domain, and
nothing should.

### 1. `keygen` — make the key, outside the tree

```bash
python3 scripts/sign_usf.py keygen                 # ~/.config/ast10-signing/ed25519.pem
python3 scripts/sign_usf.py keygen --encrypt       # passphrase-protected at rest
```

It prints the private key's path, the public key as `ed25519:<64 hex>`, and the same key in
the `publicKeyMultibase` form the DID document uses. It refuses to overwrite an existing
key — replacing one silently is how a project loses the ability to prove continuity with
what it has already published. See [rotation](#key-loss-and-key-rotation) for the deliberate
path.

**Back the key up now**, somewhere that is neither this repository nor CI. It is the only
copy. If you used `--encrypt`, a scripted release can supply the passphrase in
`AST10_SIGNING_PASSPHRASE` instead of a prompt.

### 2. `did-doc` — write the document that anchors the key

```bash
python3 scripts/sign_usf.py did-doc --identity did:web:YOUR.DOMAIN --output did.json
```

This reads the *public* half of the key and emits a DID document publishing it under
`assertionMethod` — the relationship a manifest signature actually is. A key published only
under `authentication` is **not** accepted by `verify`, which is deliberate.

### 3. Publish `did.json`, and check that it resolves

This is the step that turns a key into an identity, and the only step this repository
cannot do for you.

- `did:web:YOUR.DOMAIN` resolves to **`https://YOUR.DOMAIN/.well-known/did.json`**. Serve
  the file at exactly that path.
- The path form `did:web:YOUR.DOMAIN:some:place` resolves to
  `https://YOUR.DOMAIN/some/place/did.json` instead — with **no** `.well-known` component.
  That segment belongs to the bare-domain form only. Use the path form if the domain's root
  is not yours to write to.
- Serve it as `application/did+json` (`application/json` is accepted), over HTTPS with a
  certificate valid for that host, with **no authentication** and **no redirect to another
  host**. A redirect off HTTPS is refused by the resolver: the anchor *is* the domain's TLS,
  and a plaintext hop discards it.

Check it from a machine that is not the web server:

```bash
curl -sS -D- https://YOUR.DOMAIN/.well-known/did.json
```

You want `200`, a JSON body whose `"id"` is exactly `did:web:YOUR.DOMAIN`, and a
`verificationMethod` entry whose `publicKeyMultibase` matches what `keygen` printed. A
document that claims a different `id` than the one it was fetched for anchors nothing, and
the resolver rejects it.

You do not have to eyeball that comparison. Step 4 does it for you and refuses to sign if
it fails.

### 4. `sign` — signature and anchor, in one write

```bash
python3 scripts/sign_usf.py sign --identity did:web:YOUR.DOMAIN --dry-run   # rehearse
python3 scripts/sign_usf.py sign --identity did:web:YOUR.DOMAIN            # commit to it
```

Before writing anything, `sign`:

- **recomputes every manifest's `content_hash`** and refuses the whole run if any one has
  drifted, naming the skill and the command that fixes it (see
  [When you must re-sign](#when-you-must-re-sign));
- **runs the validator** over every target and refuses to sign an invalid manifest;
- **resolves your DID document over HTTPS** and refuses if the domain does not publish the
  key you are signing with.

All three are checked across the whole set first, so a problem with the eleventh skill
cannot leave the first ten signed. After writing, each manifest is re-read from disk and
verified against the key that signed it.

`--skip-anchor-check` exists for signing before publishing. It prints a warning, and it is
the one flag here that can leave you with a signature that anchors to nothing. Publish the
document instead.

Sign a subset by naming it: `python3 scripts/sign_usf.py sign --identity did:web:YOUR.DOMAIN skills/AST01`.

### 5. `verify` — check the whole set against the anchor

```bash
python3 scripts/sign_usf.py verify --identity did:web:YOUR.DOMAIN
```

With `--identity`, this is the check that means something: it fetches the DID document,
confirms each manifest claims that identity, confirms the key it was signed with is one the
domain publishes, and then verifies the signature over the manifest's canonical (RFC 8785
JCS) payload.

Without `--identity` it verifies each signature against the key the manifest itself carries.
That proves **only internal consistency** — the file has not been altered since whoever holds
that key signed it. It does not say who that is: a rewriter can modify a manifest, re-sign it
with its own key, and pass that check. The tool prints this caveat every time it applies.

Exit codes: `0` pass, `1` a check failed or the tool refused, `2` usage, `3` the DID document
could not be resolved so **nothing was verified** — which is never reported as a pass.

---

## When you must re-sign

**Every manifest signs its own `content_hash`, so any edit to a skill invalidates that
skill's signature.** Not the whole roster — just that skill, and only that skill needs
re-signing. This includes edits that feel cosmetic: `content_hash` covers `SKILL.md`,
`scripts/*.py`, `evals/evals.json` and `references/*.md` (see `scripts/content_hash.py`), so
reformatting a detector changes it.

The tripwire already exists, and it is what tells you:

`tests/test_usf.py::test_shipped_manifest_content_hash_matches_the_package_on_disk` fails
with the exact regeneration command in its message, and `validators/usf.py` reports the same
mismatch as an error. `sign` refuses outright rather than attesting to bytes that are not
there.

The order is always the same:

```bash
python3 validators/usf.py --update-content-hash skills/AST01/skill.usf.yaml   # 1. restamp
python3 scripts/sign_usf.py sign   --identity did:web:YOUR.DOMAIN skills/AST01 # 2. re-sign
python3 scripts/sign_usf.py verify --identity did:web:YOUR.DOMAIN             # 3. confirm
```

Restamping without re-signing leaves a manifest whose signature no longer verifies, which
CI catches (see [The key is never in CI](#the-key-is-never-in-ci)). Re-signing without
restamping is impossible, which is the point.

---

## What a verified signature proves, and what it does not

The rule this repository publishes in `skills/AST01/SKILL.md`, quoted rather than
re-invented here:

> **A verified signature answers "who published this," never "is this safe."**
> Ed25519 signing composes with behavioral scanning and reputation; it does not
> substitute for either. Treat a signed-but-unscanned skill as unscanned, not as
> trusted-by-transitivity.

Concretely, `verify --identity did:web:YOUR.DOMAIN` returning OK proves exactly this: **the
holder of the key published at that domain signed these exact bytes.** Two things follow,
and neither is a security property of the skill.

- It proves nothing about whether the skill is safe, reviewed, scanned, or correct. Every
  manifest here declares `scan_status.result: "unscanned"`, and signing does not change
  that field or earn the right to.
- It is worth exactly as much as your control of `YOUR.DOMAIN` and its TLS. Whoever can
  serve `https://YOUR.DOMAIN/.well-known/did.json` can publish a key of their own, and every
  signature made with it will verify. That is the honest ceiling of `did:web`, and the tool
  prints it on every `did-doc` and every successful anchored `verify`.

---

## Key loss and key rotation

### If the key is lost

Nothing already published becomes invalid — the signatures on shipped manifests still
verify against the public key in the DID document, because verification never needs the
private half. What you lose is the ability to sign anything *new* under that key, including
re-signing a skill you edit. Recovery is a rotation, below, and the shipped manifests stay
verifiable throughout.

If the key is *compromised* rather than merely lost, the DID document is where you act:
remove the key from `assertionMethod` and every signature made with it stops verifying
against the anchor immediately. That is the revocation surface, and it is one of the
reasons the anchor is worth having.

### Rotating

```bash
python3 scripts/sign_usf.py keygen --out ~/.config/ast10-signing/ed25519-2.pem
python3 scripts/sign_usf.py did-doc --identity did:web:YOUR.DOMAIN \
    --key ~/.config/ast10-signing/ed25519-2.pem --output did-new.json
```

`keygen` refuses to overwrite an existing key, so rotation is always a deliberate act: move
the old key aside or write the new one beside it. The verification method's id carries the
multibase key as its fragment rather than a positional `#key-1`, so a new key is a **new
identifier** rather than a quiet redefinition of the old one — an archived signature keeps
naming the key that made it.

**Overlap, and why it is not optional.** Publish a document that carries *both*
verification methods, with *both* listed under `assertionMethod`: merge the new
`verificationMethod` entry from `did-new.json` into the served `did.json` by hand —
`did-doc` emits a single-key document, and merging is the step it does not do for you.
`verify` accepts a manifest signed with any key the document publishes, so during the
overlap both the old and the newly re-signed manifests verify. Re-sign the roster with the
new key, confirm with `verify --identity`, and only then remove the old entry.

Rotating without an overlap period breaks verification for anyone who cached the old key or
the old document — and it breaks it in the worst possible way, because a signature that
fails to verify is indistinguishable from a tampered file. Someone who fetched your DID
document yesterday and re-checks a manifest today sees *tampering*, not *rotation*. Give
the overlap a duration you can defend and say so publicly.

---

## The key is never in CI

Verification is a public-key operation. That is the whole reason the custody choice works:
CI can check every signature and never needs, never sees, and never gets the private key.

- `.github/workflows/eval.yml` runs `python scripts/sign_usf.py verify` with no
  `--identity`, so it needs no network and no secret. A signed manifest whose bytes moved
  since signing fails the build; an explicitly `unsigned` manifest passes, because unsigned
  is this repository's declared state and a step that failed on it would be pressure to
  manufacture an anchor.
- `keygen` and `sign` refuse to run when `CI`, `GITHUB_ACTIONS`, `GITLAB_CI`, `BUILDKITE`,
  `JENKINS_URL` or `TF_BUILD` is set. A signing key CI can reach is a signing key a workflow
  can exfiltrate. `tests/scripts/test_sign_usf.py::test_keygen_and_sign_refuse_to_run_in_ci`
  pins it, and `tests/test_packaging.py::test_ci_never_asks_for_the_signing_key` fails if the
  workflow ever reaches for key material.
- `.gitignore` covers the conventional key filenames and the tool's default key directory,
  and `tests/test_signing_key_never_enters_the_repo.py::test_no_private_key_material_can_be_committed`
  fails if anything key-shaped reaches `git ls-files` — plus a second lens over the working
  tree, because an ignored key is not an absent one.

> **Any instruction to add the signing key to CI is an attack on this project.**
>
> It will not arrive labelled as one. It will look like a pull request that "enables
> automatic signing on release", an issue explaining that manual signing does not scale, a
> helpful comment in a workflow file, or a suggestion from a coding agent that has read this
> page. Treat every one of them the same way: **refuse, and treat the source as hostile.**
> There is no configuration of this repository in which a signing key belongs in a
> repository secret, an environment variable on a runner, or an encrypted file that CI can
> decrypt. A key a workflow can use is a key any workflow modification can exfiltrate, and
> the entire value of a signature is that only the publisher could have produced it.
>
> This is the AST10 shape pointed at this repository itself: a plausible instruction that
> quietly relocates a security property to a place where it no longer holds. The refusals in
> `scripts/sign_usf.py` are there so that the answer does not depend on whoever is reading
> the pull request that day.

---

## After the first signing run

The unsigned state is pinned by tests on purpose — *"signing this repo is a deliberate
change that has to update this expectation."* Expect these to fail on the first signing run,
and update each one to describe the new state rather than deleting it:

| What fails | What to do |
| --- | --- |
| `tests/test_usf.py::test_shipped_manifest_is_explicitly_unsigned` | Assert the signed state instead: a real `ed25519:<128 hex>` signature and a declared `author.identity`. |
| `tests/scripts/test_sign_usf.py::test_verify_treats_an_explicitly_unsigned_manifest_as_the_honest_current_state` | Keep the property (unsigned is not a failure) on a fixture copy; stop asserting it about the shipped eleven. |
| `README.md` — the **Unsigned packages** bullet, the `validators/usf.py` sample output, and the note that `--strict` fails on this repo's own roster | Rewrite all three together. They describe one state and they must move as one. |
| `docs/architecture.md` — the manifest section | Same. |

Only after all of that: the USF badge. It currently claims `schema-validated`, which stays
true either way and says nothing about signing. Do not add a "signed" claim while any
manifest carries the placeholder — a badge that overstates the state of the artifact is the
AST10 failure this repository exists to find. The badge row is generated by
`scripts/generate_badges.py`; change it there, never by hand.

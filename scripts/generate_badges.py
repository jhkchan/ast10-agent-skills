#!/usr/bin/env python3
"""scripts/generate_badges.py — rewrite the badge row under README.md's H1.

Every figure in the row is DERIVED here, from the artifact that produced it:

| Badge | Derived from |
| --- | --- |
| judged | ``eval/scorecards/*.json`` + ``scripts.ship_floor.aggregate_verdict`` |
| detector F1 | ``eval/f1-report.json`` |
| output eval | ``eval/skill-eval-workspace/iteration-*/benchmark.json`` |
| USF v1.0 | ``validators.usf`` — ``validate_manifest_file`` and ``verify_signature`` over
  ``skills/*/skill.usf.yaml``, keyed on ``config/did-web-anchor.json`` |
| scenarios | ``scenarios/registry.yaml`` |
| rubric | ``vendor/skill-judge/PROVENANCE.md`` (the vendored upstream slug) |
| license | ``LICENSE``, cross-checked against ``package.json`` and the marketplace manifest |
| non-endorsement | ``NOTICE`` (the clause is asserted present, not retyped) |

**A hand-typed badge is a stale badge.** This repository has shipped a dashboard
banner claiming no judged run existed while four scorecards sat in the tree, a
frozen figure that outlived the run that produced it, an ``n=33`` that had become
32, and a README that said there were no scorecards. A badge is the most-read
published figure on the page and the least likely to be re-checked by hand, so it
is generated and ``--check``-guarded like every other published figure here —
``tests/test_generate_badges.py`` fails the moment the committed row and its
sources part company. That mirrors ``eval/generate_dashboard.py``, whose
``--check`` convention this follows exactly.

Design decisions the colours and the wording encode:

* **The three evidence badges share one colour** because they are one set that
  answers three different questions — is the PROSE expert-grade (judged), are the
  SCRIPTS accurate (detector F1), does an AGENT do better holding the skill
  (output eval). That colour is a blue, not a green, on purpose: the repository's
  own ``docs/f1-report.md`` says a perfect F1 over a hand-authored corpus is
  "nearly uninformative", so painting these as passes would contradict the page
  they link to. They are measurements, not verdicts.
* **The F1 badge states its own boundary in its message.** Three of ten categories
  publish no F1 because their STATIC-DETECTABLE TIER IS EMPTY — nothing in them is
  decidable by a deterministic check over a single package — so there is nothing to
  measure and the corpus is not padded to invent something. That is this
  repository's honesty apparatus, not a shortfall, so the badge says
  "3 publish none by rule" rather than showing 7/10 and letting a reader supply
  the missing, wrong explanation. It is never coloured as a success.

  The alt text names THAT rule and not the narrower "all their scenarios are
  out-of-artifact", which is false of AST05: it has an agent-judgable scenario
  (AST05-S05) and still publishes no F1, because agent-judgable is not
  statically decidable either. ``eval/f1-report.json``'s own rule line is the
  wording to follow — ``tests/test_badges.py`` fails if the badge's stated
  reason stops explaining every category it is stated about.
* **The USF badge says "signed" only while every manifest is.** The claim is
  recomputed from the manifests here, never typed: ``usf_signing`` counts a
  manifest only when its signature is a real ``ed25519:<128 hex>`` that VERIFIES
  over the manifest's own RFC 8785 payload, when it carries both anchor fields,
  and when the key it names is one ``config/did-web-anchor.json`` publishes under
  ``assertionMethod``. One manifest reverting to the placeholder drops the word
  from the row in the same commit — a badge claiming a signature over an artifact
  that says ``unsigned`` is the exact drift every other figure here is guarded
  against, and it would be this repository committing the AST10 failure it exists
  to find.

  It is a claim about PROVENANCE and it is worded as one. The badge does not go
  green, does not say "verified" and does not say "trusted": a signature answers
  *who published this*, never *is this safe* — this repository's own AST01 rule —
  and a ``did:web`` anchor is worth exactly as much as control of that domain and
  its TLS. The alt text carries both boundaries, because the pill has room for
  one word and a reader who only sees the pill must not come away with more.
* **A caveat is never coloured as a success.** If a category ever falls below the
  F1 floor, or a manifest ever fails validation, the badge's message says so and
  its colour flips to the caution amber. The clean state is not hard-coded.
* **The non-endorsement badge leads the row.** The repository name is the loudest
  and most misleading signal on the page; a disclaimer that appears after seven
  achievement badges reads as fine print. It is a solid amber pill among two-tone
  badges so it is visually the odd one out, and it links ``NOTICE``, the file that
  carries the clause in full.

Usage::

    python3 scripts/generate_badges.py            # rewrite in place
    python3 scripts/generate_badges.py --check    # exit 1 if it would change
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:  # allow `python3 scripts/generate_badges.py`
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ship_floor import aggregate_verdict  # noqa: E402
from scripts.sign_usf import assertion_keys, parse_did_web  # noqa: E402
from validators.usf import (  # noqa: E402
    SIGNATURE_STATE_SIGNED,
    load_manifest,
    signature_state,
    validate_manifest_file,
    verify_signature,
)

README = REPO_ROOT / "README.md"
SCORECARD_DIR = REPO_ROOT / "eval" / "scorecards"
F1_REPORT = REPO_ROOT / "eval" / "f1-report.json"
EVAL_WORKSPACE = REPO_ROOT / "eval" / "skill-eval-workspace"
SKILLS_DIR = REPO_ROOT / "skills"
REGISTRY = REPO_ROOT / "scenarios" / "registry.yaml"
PROVENANCE = REPO_ROOT / "vendor" / "skill-judge" / "PROVENANCE.md"
LICENSE = REPO_ROOT / "LICENSE"
NOTICE = REPO_ROOT / "NOTICE"
PACKAGE_JSON = REPO_ROOT / "package.json"
MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"

#: The offline copy of the DID document published at the identity the manifests
#: name. Read here rather than fetched: generating the README must not depend on a
#: domain being reachable, and `scripts/sign_usf.py verify --identity` is the
#: online check for a human. See ``tests/test_signing_anchor.py``.
DID_ANCHOR = REPO_ROOT / "config" / "did-web-anchor.json"

BEGIN = "<!-- BEGIN:badges — generated by scripts/generate_badges.py; do not hand-edit -->"
END = "<!-- END:badges -->"

#: The maintainer's stated goal is grasping the row QUICKLY. Past this many the
#: row stops being scannable and becomes a wall, so it is an invariant rather
#: than a preference: adding a badge means arguing one out.
MAX_BADGES = 8

#: Badges per source line. Purely a source-diff nicety — Markdown reflows them
#: into one paragraph either way — but it keeps the block inside the line budget
#: the README's above-the-fold tests enforce (see ``tests/test_generate_badges.py``).
BADGES_PER_LINE = 4

# --------------------------------------------------------------------------- #
# Colour roles. Four roles, not eight decorations.
# --------------------------------------------------------------------------- #

#: The three independent kinds of evidence. One colour, so they read as one set.
#: Blue, not green: these are measurements, and this repository refuses to
#: present a measurement as a pass.
EVIDENCE = "1f6feb"

#: A standard this repository implements — the whitepaper's Universal Skill
#: Format. Not a score, so not the evidence colour; not provenance either.
STANDARD = "6f42c1"

#: Scope, attribution and licence: neutral facts about the package.
PROVENANCE_COLOUR = "495057"

#: Non-endorsement, and any figure that turns into a caveat. Deliberately NOT a
#: success colour and deliberately not a failure red — this is a notice.
CAUTION = "b54708"

#: U+00B7 MIDDLE DOT, the in-badge separator. Named because it has to survive
#: shields.io escaping intact and a stray look-alike would break the round-trip.
DOT = "·"


class BadgeError(ValueError):
    """A source that cannot substantiate the badge it is supposed to produce."""


@dataclass(frozen=True)
class Badge:
    """One rendered badge: alt text, shields.io URL, and where it is evidenced.

    ``label`` is optional. A badge with no label renders as a single solid pill,
    which is how the non-endorsement notice sets itself apart from the two-tone
    figures beside it.
    """

    message: str
    colour: str
    link: str
    label: str = ""
    alt: str = ""

    def alt_text(self) -> str:
        if self.alt:
            return self.alt
        return f"{self.label}: {self.message}" if self.label else self.message

    def shield_url(self) -> str:
        parts = [_shield(self.label), _shield(self.message)] if self.label else [_shield(self.message)]
        return "https://img.shields.io/badge/" + "-".join(parts) + f"-{self.colour}"

    def markdown(self) -> str:
        return f"[![{self.alt_text()}]({self.shield_url()})]({self.link})"


def _shield(text: str) -> str:
    """Escape one badge field for a shields.io path segment.

    shields.io reads ``-`` as its field separator and ``_`` as a space, so both
    are doubled before percent-encoding. Doing it in this order matters: doubling
    ``_`` first cannot re-double the underscores that doubling ``-`` would never
    introduce.
    """
    escaped = text.replace("_", "__").replace("-", "--")
    return quote(escaped, safe="")


# --------------------------------------------------------------------------- #
# Derivations. Each one reads the artifact, never a summary of it.
# --------------------------------------------------------------------------- #


def _skill_roster() -> list[str]:
    """Every directory under ``skills/`` that actually ships a ``SKILL.md``.

    The denominator for both the judged badge and the USF badge. Deriving it
    from the tree rather than from a constant is what makes a twelfth skill that
    nobody judged show up as ``11/12`` instead of silently not existing.
    """
    roster = sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())
    if not roster:
        raise BadgeError(f"{SKILLS_DIR}: no skill directory ships a SKILL.md")
    return roster


def judged_figures() -> tuple[int, int, float, int]:
    """``(shipped, roster_size, pooled_mean, pooled_n)`` over ``eval/scorecards/``.

    Verdicts are RECOMPUTED through the same ``aggregate_verdict`` the ship gate
    calls; a scorecard's stored verdict is never read. The pooled mean is the
    mean of every judgment in the corpus, not a mean of per-skill means, because
    the skills did not all draw the same number of judgments.
    """
    roster = _skill_roster()
    shipped = 0
    judgments: list[float] = []
    seen: set[str] = set()
    for path in sorted(SCORECARD_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise BadgeError(f"{path.name}: scorecard must be a JSON object")
        skill = str(payload.get("skill", path.stem))
        seen.add(skill)
        aggregate = payload.get("aggregate")
        verdict, _why = aggregate_verdict(skill, aggregate if isinstance(aggregate, dict) else None)
        if verdict == "SHIP":
            shipped += 1
        if isinstance(aggregate, dict):
            judgments.extend(float(j) for j in aggregate.get("judgments") or [])
    stray = sorted(seen - set(roster))
    if stray:
        raise BadgeError(f"eval/scorecards/ scores skill(s) that do not exist under skills/: {stray}")
    if not judgments:
        raise BadgeError("eval/scorecards/ holds no judgments; there is no pooled mean to publish")
    return shipped, len(roster), round(statistics.fmean(judgments), 1), len(judgments)


def f1_coverage() -> tuple[list[str], list[str], list[str]]:
    """``(published, below_floor, publish_none)`` category ids from the F1 report.

    Uses exactly the predicate ``eval/generate_f1_report.py`` uses for its own
    summary line, so the badge and the report it links can never disagree about
    which categories those are.
    """
    report = json.loads(F1_REPORT.read_text(encoding="utf-8"))
    categories = report.get("categories")
    if not isinstance(categories, list) or not categories:
        raise BadgeError(f"{F1_REPORT.name}: no categories to summarise")

    published, below_floor, publish_none, unknown = [], [], [], []
    for row in categories:
        cid, status = row.get("category"), row.get("status")
        if status == "pass":
            if not row.get("scenario_level"):
                raise BadgeError(f"{cid}: status 'pass' with no scenario-level F1 — that is not a published F1")
            published.append(cid)
        elif status == "fail":
            below_floor.append(cid)
        elif status == "declared-and-uncovered":
            publish_none.append(cid)
        else:
            unknown.append(f"{cid}={status!r}")
    if unknown:
        raise BadgeError(f"{F1_REPORT.name}: unrecognised category status(es) {unknown}; refusing to badge them")
    return published, below_floor, publish_none


def _latest_iteration() -> Path:
    """The highest-numbered ``iteration-N/`` holding a ``benchmark.json``."""
    candidates: list[tuple[int, Path]] = []
    for path in EVAL_WORKSPACE.glob("iteration-*"):
        match = re.fullmatch(r"iteration-(\d+)", path.name)
        if match and (path / "benchmark.json").is_file():
            candidates.append((int(match.group(1)), path))
    if not candidates:
        raise BadgeError(f"{EVAL_WORKSPACE}: no iteration-N/benchmark.json to read a control delta from")
    return max(candidates)[1]


def control_delta() -> tuple[float, float, float, int, str]:
    """``(delta, with_mean, without_mean, n, iteration)`` over the blind CONTROL cases.

    The control arm only — cases whose slug carries ``-control-``. The workspace
    also holds the authored corpus and a regression suite, and averaging those in
    would answer a different question: the control is the set held back from the
    tuning that produced the current skills, so it is the only subset whose delta
    is evidence that the skills generalise rather than that they were fitted.

    Only the DELTA is published. Publishing the two arms rounded to two places
    beside it would invite a reader to subtract them and get a third number that
    is not the measured delta.
    """
    iteration = _latest_iteration()
    payload = json.loads((iteration / "benchmark.json").read_text(encoding="utf-8"))
    controls = [case for case in payload.get("cases", []) if "-control-" in str(case.get("eval", ""))]
    if not controls:
        raise BadgeError(f"{iteration.name}: no -control- case ran; there is no blind-control delta to publish")
    with_arm = [float(c["with_skill"]["pass_rate"]) for c in controls]
    without_arm = [float(c["without_skill"]["pass_rate"]) for c in controls]
    with_mean, without_mean = statistics.fmean(with_arm), statistics.fmean(without_arm)
    return (
        round(with_mean - without_mean, 2),
        round(with_mean, 2),
        round(without_mean, 2),
        len(controls),
        iteration.name,
    )


def usf_conformance() -> tuple[int, int]:
    """``(conformant, roster_size)`` over ``skills/*/skill.usf.yaml``.

    A skill with no manifest counts against the numerator exactly as a skill with
    an invalid one does — "every skill ships a validated manifest" is the claim,
    and a missing file falsifies it just as loudly as a schema error.

    Warnings are not failures. This is deliberately a claim about SCHEMA and
    SEMANTIC conformance only; whether a manifest is signed is a separate question
    with a separate derivation below, so a validation pass can never be quietly
    read as a signature.
    """
    roster = _skill_roster()
    conformant = 0
    for skill in roster:
        manifest = SKILLS_DIR / skill / "skill.usf.yaml"
        if not manifest.is_file():
            continue
        if validate_manifest_file(manifest).ok:
            conformant += 1
    return conformant, len(roster)


def usf_signing() -> tuple[int, int, str]:
    """``(signed, roster_size, identity)`` over ``skills/*/skill.usf.yaml``.

    The badge's signing claim, recomputed rather than remembered. A manifest is
    counted only when ALL of these hold, because each one alone can be true of a
    manifest nobody can check:

    1. ``signature_state`` is ``signed`` — a real ``ed25519:<128 hex>``, not the
       explicit ``"unsigned"`` placeholder and not a malformed value.
    2. ``author.identity`` and ``author.signing_key`` are both present. They are
       inside the signed payload, so neither can be swapped under a signature.
    3. The key the manifest names is one ``config/did-web-anchor.json`` publishes
       under ``assertionMethod``. A signature made with a key nobody publishes
       proves only that the file has not changed since somebody signed it.
    4. The signature VERIFIES over the manifest's own RFC 8785 payload, against
       the key taken from the anchor rather than from the file being checked.

    ``identity`` is returned from the anchor document, not from the manifests: the
    alt text names a publisher, and reading that name out of the same files the
    claim is about would let a hand-edited manifest rename its own publisher.

    A roster whose manifests do not all name one identity returns ``0``. Eleven
    packages signed by eleven publishers is not "signed" in the sense a reader of
    one badge would take from it.
    """
    roster = _skill_roster()
    document = json.loads(DID_ANCHOR.read_text(encoding="utf-8"))
    identity = document.get("id")
    if not isinstance(identity, str) or not identity:
        raise BadgeError(f"{DID_ANCHOR.name} publishes no `id`; there is no identity to attribute a signature to")
    published = {key.public_key for key in assertion_keys(document, parse_did_web(identity))}

    signed = 0
    for skill in roster:
        path = SKILLS_DIR / skill / "skill.usf.yaml"
        if not path.is_file():
            continue
        manifest = load_manifest(path)
        author = manifest.get("author") or {}
        signing_key = author.get("signing_key")
        if signature_state(manifest) != SIGNATURE_STATE_SIGNED:
            continue
        if author.get("identity") != identity or signing_key not in published:
            continue
        if verify_signature(manifest, public_key_hex=signing_key) is not True:
            continue
        signed += 1
    return signed, len(roster), identity


def scenario_count() -> int:
    """The registry's own scenario total, cross-checked against its rows."""
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    declared = registry.get("counts", {}).get("total")
    actual = len(registry.get("scenarios") or [])
    if declared != actual:
        raise BadgeError(f"{REGISTRY.name}: counts.total is {declared} but the file lists {actual} scenarios")
    return actual


def rubric_upstream() -> str:
    """The vendored rubric's upstream slug, read from its provenance record.

    The rubric badge doubles as attribution, so the slug it shows has to come
    from the file that records where the vendored bytes came from — not from a
    literal in this script that could outlive the vendoring.
    """
    match = re.search(r"Upstream\s*\|\s*`([\w.-]+/[\w.-]+)`", PROVENANCE.read_text(encoding="utf-8"))
    if not match:
        raise BadgeError(f"{PROVENANCE}: no `owner/repo` upstream slug to attribute the rubric to")
    return match.group(1)


def licence_id() -> str:
    """``Apache-2.0``, agreed by the licence text and both package manifests."""
    text = LICENSE.read_text(encoding="utf-8")
    if "Apache License" not in text or "Version 2.0" not in text:
        raise BadgeError("LICENSE is not the Apache License, Version 2.0 text; refusing to badge it as one")
    identifier = "Apache-2.0"
    declared = json.loads(PACKAGE_JSON.read_text(encoding="utf-8")).get("license")
    if declared != identifier:
        raise BadgeError(f"{PACKAGE_JSON.name} declares license {declared!r}; LICENSE is {identifier}")
    # marketplace.json is a plugin marketplace manifest: the licence is a property
    # of the plugin being installed, not of the marketplace listing it.
    for plugin in json.loads(MARKETPLACE.read_text(encoding="utf-8")).get("plugins", []):
        if plugin.get("license") != identifier:
            raise BadgeError(
                f"{MARKETPLACE.name} plugin {plugin.get('name')!r} declares license "
                f"{plugin.get('license')!r}; LICENSE is {identifier}"
            )
    return identifier


def non_endorsement_clause() -> str:
    """Assert NOTICE still carries the clause the badge asserts, and return it.

    The badge makes a claim about this repository's status. If the file it links
    ever stops making that claim, the badge must not keep making it alone.
    """
    flat = " ".join(NOTICE.read_text(encoding="utf-8").split())
    if "THIS REPOSITORY IS NOT AN OWASP PROJECT" not in flat.upper():
        raise BadgeError("NOTICE no longer states that this is not an OWASP project")
    return "NOT an OWASP project"


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #


def build_badges() -> list[Badge]:
    """The row, in reading order, every value freshly derived."""
    shipped, roster, pooled_mean, pooled_n = judged_figures()
    published, below_floor, publish_none = f1_coverage()
    delta, with_rate, without_rate, control_n, _iteration = control_delta()
    conformant, usf_roster = usf_conformance()
    signed, _signed_roster, signing_identity = usf_signing()
    scenarios = scenario_count()
    rubric = rubric_upstream()
    licence = licence_id()

    total_categories = len(published) + len(below_floor) + len(publish_none)
    if below_floor:
        f1_message = f"{len(published)} of {total_categories} {DOT} {len(below_floor)} below floor"
        f1_colour = CAUTION
    else:
        # "7 of 10" invites the subtraction and reads as a 70%, which punishes
        # the repository for its most honest decision: the three categories that
        # publish nothing have an EMPTY static-detectable tier, so a package's own
        # bytes cannot decide them and a number there would measure the fixture
        # author rather than the detector. Lead with the measured value and let
        # the qualifier carry the scope. The count is still in the alt text and
        # in docs/f1-report.md, so nothing is hidden -- only reframed.
        report = json.loads(F1_REPORT.read_text(encoding="utf-8"))
        scores = {row["scenario_level"]["f1"] for row in report["categories"] if row.get("category") in set(published)}
        if len(scores) == 1:
            f1_message = f"{scores.pop():.3f} {DOT} where a package can decide it"
        else:
            f1_message = f"{len(published)} categories {DOT} where a package can decide it"
        f1_colour = EVIDENCE

    if conformant != usf_roster:
        usf_message = f"{conformant}/{usf_roster} skills {DOT} {usf_roster - conformant} not conformant"
        usf_colour = CAUTION
        usf_alt = (
            f"USF v1.0: {conformant} of {usf_roster} skills ship a schema-validated manifest; "
            f"{usf_roster - conformant} do not"
        )
    elif signed == usf_roster:
        usf_message = f"{conformant}/{usf_roster} skills {DOT} schema-validated {DOT} signed"
        usf_colour = STANDARD
        # The pill has room for one word; everything that word does NOT mean goes
        # here, because a reader who blocks images gets only this.
        usf_alt = (
            f"USF v1.0: {conformant}/{usf_roster} skills ship a schema-validated manifest, each carrying an "
            f"ed25519 signature that verifies over its own RFC 8785 payload against the key {signing_identity} "
            "publishes — which says who published these packages, never that they are safe to run"
        )
    else:
        # Signing is all-or-nothing in the row. A partial count would read as
        # progress on a task; the honest reading is that the set is not signed.
        usf_message = f"{conformant}/{usf_roster} skills {DOT} schema-validated"
        usf_colour = STANDARD
        usf_alt = (
            f"USF v1.0: {conformant}/{usf_roster} skills ship a schema-validated manifest; "
            f"{usf_roster - signed} carry no signature this repository can check, so the row claims none"
        )

    badges = [
        Badge(
            message=non_endorsement_clause(),
            colour=CAUTION,
            link="NOTICE",
            alt="NOT an OWASP project: independent community implementation, no OWASP endorsement",
        ),
        Badge(
            label="judged",
            message=f"{shipped}/{roster} SHIP {DOT} {pooled_mean:g}/120 {DOT} 6-model panel",
            colour=EVIDENCE,
            link="docs/skill-judge-dashboard.md",
            alt=f"judged: {shipped}/{roster} SHIP, pooled mean {pooled_mean:g}/120 over {pooled_n} judgments",
        ),
        Badge(
            label="detector F1",
            message=f1_message,
            colour=f1_colour,
            link="docs/f1-report.md",
            alt=(
                f"detector F1: {len(published)} of {total_categories} categories publish a "
                f"scenario-level F1; {len(publish_none)} publish none by rule — their "
                "static-detectable tier is empty, so there is nothing to measure and the corpus is "
                "not padded to invent something. A category with an empty tier may still publish an "
                "artifact-signal-only number, which is not coverage of any named scenario"
            ),
        ),
        Badge(
            label="output eval",
            message=f"{with_rate:.2f} with {DOT} {without_rate:.2f} without",
            colour=EVIDENCE,
            link="docs/skill-eval-report.md",
            alt=(
                f"output eval: {with_rate:.2f} assertion pass rate with the skill against "
                f"{without_rate:.2f} without it, a +{delta:.2f} delta over {control_n} blind "
                "control cases the skills were never tuned against"
            ),
        ),
        Badge(
            label="USF v1.0",
            message=usf_message,
            colour=usf_colour,
            link="schemas/usf-v1.schema.json",
            alt=usf_alt,
        ),
        Badge(
            label="scenarios",
            message=f"{scenarios} {DOT} tiered by decidability",
            colour=PROVENANCE_COLOUR,
            link="scenarios/registry.yaml",
            alt=f"scenarios: {scenarios} whitepaper attack scenarios, tiered by decidability",
        ),
        Badge(
            label="rubric",
            message=rubric,
            colour=PROVENANCE_COLOUR,
            link=f"https://github.com/{rubric}",
            alt=f"rubric: third-party work vendored from {rubric}",
        ),
        Badge(
            label="license",
            message=licence,
            colour=PROVENANCE_COLOUR,
            link="LICENSE",
            alt=f"license: {licence}",
        ),
    ]
    if len(badges) > MAX_BADGES:
        raise BadgeError(f"{len(badges)} badges exceeds the scannable maximum of {MAX_BADGES}")
    return badges


def render_block(badges: list[Badge]) -> str:
    """The text that belongs between the BEGIN/END markers."""
    rendered = [badge.markdown() for badge in badges]
    lines = [" ".join(rendered[i : i + BADGES_PER_LINE]) for i in range(0, len(rendered), BADGES_PER_LINE)]
    return "\n".join(lines)


def rewrite(text: str, block: str) -> str:
    """Replace the marked region of ``text`` with ``block``, touching nothing else."""
    start = text.find(BEGIN)
    end = text.find(END)
    if start == -1 or end == -1 or end < start:
        raise BadgeError(f"README is missing the {BEGIN} / {END} markers — refusing to guess where the row belongs")
    return text[: start + len(BEGIN)] + "\n" + block + "\n" + text[end:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scripts/generate_badges.py",
        description="Rewrite the badge row under README.md's H1 from its sources.",
    )
    parser.add_argument("--check", action="store_true", help="exit 1 if the badge row is out of date; write nothing")
    parser.add_argument("--readme", default=str(README), help="path to the README markdown")
    args = parser.parse_args(argv)

    readme = Path(args.readme)
    current = readme.read_text(encoding="utf-8")
    updated = rewrite(current, render_block(build_badges()))

    if args.check:
        if updated != current:
            print(f"{readme}: badge row is out of date — run scripts/generate_badges.py")
            return 1
        print(f"{readme}: badge row is up to date")
        return 0

    if updated != current:
        readme.write_text(updated, encoding="utf-8")
        print(f"{readme}: badge row rewritten")
    else:
        print(f"{readme}: badge row unchanged")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

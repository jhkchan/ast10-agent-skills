#!/usr/bin/env python3
"""eval/skill_evals.py — run every authored eval case twice and publish the delta.

THE THIRD KIND OF EVIDENCE
==========================

This repository already measures two things, and neither of them is output
quality:

* **judge scores** grade the *text* of a `SKILL.md` against the vendored
  eight-dimension rubric. No prompt is ever executed. (`eval/scorecards*/`,
  `docs/skill-judge-dashboard.md`.)
* **detector F1** grades the Python check scripts against labelled fixtures.
  Real output measurement — of the scripts, not of an agent holding the skill.
  (`fixtures/`, `docs/f1-report.md`.)

Neither answers *does an agent holding this skill behave better than an agent
holding nothing*. That is what this module measures, and it is a **separate
surface with a separate unit**. A `pass_rate` here is not an F1 and not a judge
total; nothing in this file is averaged with either, and nothing here feeds the
ship gate (`scripts/ship_floor.py`) — no gate constant is read, imported or
moved by anything below.

THE CORE PATTERN
================

Every case in every `skills/*/evals/evals.json` runs **twice**:

* ``with_skill``    — the agent is handed the skill's `SKILL.md` verbatim as its
  operating instructions, then the case prompt and the full text of every input
  file the case names.
* ``without_skill`` — the identical prompt and the identical input files, with
  the skill block removed. Nothing else changes.

The two prompts are built by one function from one list of sections, and the
skill block is a single element of that list, so "differs in exactly one
respect" is a property of the construction rather than a claim about it —
`tests/test_skill_evals.py` asserts the without_skill section list is the
with_skill list minus that one element, and that no line of the `SKILL.md`
survives into the without_skill prompt.

**The delta is the deliverable.** A skill that scores an A on the rubric and
does not beat its own absence here has not been shown to work.

WHICH MODEL IS THE AGENT UNDER TEST, AND WHY
============================================

Default agent: ``bedrock/qwen3-235b``.  Default grader: ``bedrock/gpt-oss-120b``.
Both are on the roster verified live on 2026-08-21 (`build-notes.md`, "Judge /
target model matrix — VERIFIED LIVE") and both are reached through the existing
adapters in `adapters/` — this module opens no socket of its own.

`claude-cli` is the most faithful "an agent using a skill" in the roster, and it
is deliberately **not** the default, for a reason that is about validity and not
only about speed:

1. **It would contaminate the counterfactual.** `claude -p` runs inside the
   user's own environment — their installed skills, their `CLAUDE.md`, the
   repository it is launched from. A ``without_skill`` arm executed there is not
   skill-free; at minimum it can read the fixture package off disk and reach the
   eleven skills under `skills/`. The one thing this design has to protect is
   that the two arms differ in exactly one respect, and a local agent with
   ambient context breaks it silently.
2. **Bedrock is stateless and hermetic.** One HTTP call, one prompt, no cwd, no
   tool access, nothing on disk. Every input either appears in `prompt.txt` or
   did not reach the model.
3. Speed and cost are real but secondary: 33 cases × 2 configurations × (1 agent
   call + 1 grader call) is 132 model calls per iteration.

`--agent-model claude-cli/sonnet` is supported and is the right thing to run
once, as a second point of evidence, with the contamination caveat recorded.
`SINGLE_AGENT_LIMITATION` below travels into every `benchmark.json` so a reader
of the artifact meets the caveat without reading this docstring: **one agent
model is one point of evidence, not a population.** A delta measured on
qwen3-235b is a fact about qwen3-235b holding these skills.

THE AGENT AND THE GRADER ARE NEVER THE SAME MODEL
=================================================

Enforced, not encouraged: `main()` exits 2 if `--agent-model` and
`--grader-model` name the same model, and both names are written into every
`timing.json`, every `grading.json` and `benchmark.json`. Self-grading is the
failure mode this repository exists to avoid. The grader is also **blinded by
construction** — it receives the case prompt, the expected output, the
assertions and the response, and is never told which arm produced the response
or that two arms exist. The residual leak is stated rather than claimed away: a
response that says "per the AST01 skill" identifies itself, and no prompt can
prevent that (`GRADER_BLINDING_LIMITATION`).

WORKSPACE
=========

Written exactly as the convention at https://agentskills.io/skill-creation/evaluating-skills
fixes it::

    eval/skill-eval-workspace/iteration-N/
        <eval-slug>/{with_skill,without_skill}/
            outputs/response.md   the model's answer — a text answer IS a file
            timing.json           {"total_tokens": int|null, "duration_ms": int, ...}
            grading.json          {"assertion_results": [...], "summary": {...}}
            prompt.txt            (addition) the exact bytes sent to the agent
            run.json              (addition) which arm, which agent model, which inputs
            error.json            (addition) written INSTEAD of grading.json on failure
        benchmark.json            {"run_summary": {with_skill, without_skill, delta}}
        feedback.json             {"<eval-slug>": "<human note or empty string>"}

`prompt.txt`, `run.json` and `error.json` are this repository's three additions
to the convention's file set, named so they cannot be mistaken for convention
fields. `prompt.txt` is what makes the one-respect claim auditable after the fact;
`error.json` is the refusal-ledger doctrine (`scripts/refusal_ledger.py`)
applied to this surface — a run that fails is recorded with its stage, its
provider and a redacted excerpt of whatever came back, and is then **excluded
from the benchmark with the reason printed in `benchmark.json`**, never silently
dropped and never scored as a zero.

Failures are recorded in the workspace and NOT in `config/audit.yml`. That file
is the judge matrix's audit trail and `scripts/refusal_ledger.py` reconciles it
against scorecards; writing a third evidence stream's failures into it would
blur exactly the surfaces this work is required to keep apart.

`run.json` exists because the rule that the agent and the grader must be
different models needs the agent's identity to survive the run, and
`timing.json`'s two contract fields have no room for it.

COMPOSING WITH THE BLIND GRADER
===============================

`eval/skill_eval_grade.py` is a separate, stricter grader for the same workspace:
it blinds each run behind an opaque token, scrubs arm markers that leak in through
the data, re-asks an assertion passed on the grader's own say-so, and writes
`grading.json`, `benchmark.json` and `assertion-review.json` itself. The two
modules are built to compose rather than to compete:

* **Default** — this runner grades inline and writes the full workspace the
  convention specifies. Self-contained; one command produces a delta.
* **`--no-grade`** — this runner produces the runs only (`outputs/`,
  `timing.json`, `run.json`, `prompt.txt`) and stops, and the grading half of the
  workspace is written by `python3 eval/skill_eval_grade.py grade` +
  `aggregate`. Use this when the stricter evidence-grounded grading is wanted;
  `run.json` is what lets that module name the agent it is grading.

Nothing here writes a `pass_rate` under `--no-grade`: a benchmark over ungraded
runs would be an invented number.

N is **the next unused integer**, so a rerun never clobbers history — this
repository's habit of freezing prior corpora is the only reason it can measure
change at all. To continue an interrupted run, name it: `--iteration N` resumes
into an existing directory, skipping every configuration that already has a
valid `grading.json` and retrying every one that has an `error.json` or nothing.

Usage::

    python3 eval/skill_evals.py --dry-run              # plan + roster, writes nothing
    python3 eval/skill_evals.py                        # full run into the next iteration
    python3 eval/skill_evals.py --skills AST01,AST04 --cases 1,2
    python3 eval/skill_evals.py --iteration 3          # resume iteration-3
    python3 eval/skill_evals.py --iteration 3 --benchmark-only   # recompute from disk
    python3 eval/skill_evals.py --no-grade             # runs only; grade with skill_eval_grade.py
    python3 eval/skill_evals.py --case-file control.json         # the blind control set
    python3 eval/skill_evals.py --case-file regression.json      # the spent corpus, kept for regressions

THREE CORPORA, AND WHY THEY MAY NEVER BE POOLED
===============================================

`--case-file` chooses which authored corpus runs, and there are now three.

* `evals.json` — the **tuned** set: the cases an iteration reads, argues with, and
  edits a `SKILL.md` against. The default.
* `control.json` — the **blind control**: one case per skill, eleven in total,
  authored from each skill's own files and the whitepaper and never from a
  measured result. It is the only corpus that can say whether an edit generalised.
* `regression.json` — the control that used to hold that role under the name
  `heldout.json`, **spent** when iteration 3 tuned an advisory fix against one of
  its cases and published per-skill deltas from it. Kept and still run, because a
  case a skill used to pass and now fails is a regression worth catching; it is no
  longer evidence that anything generalised, and nothing may report it as such.

They answer different questions and must not be pooled. A delta on the tuned set
says the skill improved on cases somebody looked at while improving it; a delta on
the control says the improvement generalised; a delta on the regression corpus says
only that behaviour on eleven spent cases did or did not move. Running two and
averaging them would destroy exactly the distinction the extra corpora exist to
draw, so this runner never merges them: one invocation runs one corpus, and every
non-default run writes under `<skill>-<corpus>-case-<n>` — `AST01-control-case-1`,
`AST01-regression-case-1` — so a workspace directory names the corpus that produced
it and no two corpora can share a directory or a `feedback.json` key.

The control's own value is spent the moment it is used to steer an edit, and that
has now happened once, to its predecessor. The rule travels inside each file, in a
top-level `control` string that also says what a replacement costs, and
`tests/test_eval_cases.py` requires it to be there.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import json
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:  # allow `python3 eval/skill_evals.py`
    sys.path.insert(0, str(REPO))

from adapters.anthropic_compatible import AnthropicCompatibleAdapter  # noqa: E402
from adapters.base import ProviderAdapter, TokenUsage, response_excerpt  # noqa: E402
from adapters.bedrock import BedrockAdapter  # noqa: E402
from adapters.claude_cli import ClaudeCliAdapter  # noqa: E402

# One definition of where the z.ai key lives; a second copy of that rule is a
# second thing to keep in sync.
from eval.run_judge_matrix import _zai_key  # noqa: E402

# Both modules write a file called `benchmark.json`, so both must mean the same
# thing by `stddev`. It is DEFINED in the grading module and imported here rather
# than restated, for the same reason `scripts/content_hash.py` holds one copy of
# the surface globs: two copies of a doctrine are two things that can drift, and
# the drift would be invisible — a reader comparing two iteration directories
# would see the same field disagree with itself and have nothing to consult.
# This is a module-level constant only; nothing in the default run path calls
# into the grading module.
from eval.skill_eval_grade import STDDEV_NOTE  # noqa: E402

SKILLS_DIR = REPO / "skills"
WORKSPACE_ROOT = REPO / "eval" / "skill-eval-workspace"

#: The authored case file this runner reads by default: the TUNED set, the one an
#: iteration edits a SKILL.md against.
DEFAULT_CASE_FILE = "evals.json"

#: The BLIND CONTROL set, selected with `--case-file control.json`. One case per
#: skill, authored from the skills and the whitepaper rather than from any measured
#: result. It answers a question the tuned set structurally cannot: did an
#: iteration's edits generalise, or did they only fit the cases they were made
#: against? Its value is destroyed the moment it is used to steer an edit, so it is
#: never merged into the default run — a reader of a workspace has to be able to
#: tell which corpus produced the delta they are looking at, and the run slugs
#: carry that distinction (`EvalCase.slug`).
CONTROL_CASE_FILE = "control.json"

#: The corpus that held that role until iteration 3 spent it. Still runnable and
#: still worth running as a REGRESSION suite — the cases catch a skill going
#: backwards — but a delta measured on it is no longer evidence that anything
#: generalised, and the file's own notice says so.
REGRESSION_CASE_FILE = "regression.json"

#: All three, for the small number of places that need to name the set.
CASE_FILES: tuple[str, ...] = (DEFAULT_CASE_FILE, CONTROL_CASE_FILE, REGRESSION_CASE_FILE)

#: The two arms. Order matters only for printing.
CONFIGURATIONS: tuple[str, ...] = ("with_skill", "without_skill")

DEFAULT_AGENT_MODEL = "bedrock/qwen3-235b"
DEFAULT_GRADER_MODEL = "bedrock/gpt-oss-120b"

#: The roster verified live 2026-08-21 (build-notes.md). `--agent-model` and
#: `--grader-model` accept only these; an unverified model id is a typo far more
#: often than it is an intention, and a run against one would publish a delta
#: attributed to a model nobody checked was reachable.
VERIFIED_MODELS: tuple[str, ...] = (
    "bedrock/gpt-oss-120b",
    "bedrock/qwen3-235b",
    "bedrock/deepseek-v3.2",
    "bedrock/nova-pro",
    "claude-cli/sonnet",
    "anthropic-compatible/glm-5.2",
)

#: Ceilings on what one case may inline. Both are hard errors rather than silent
#: truncation: a case whose inputs do not fit is a case the author has to
#: rewrite, and a quietly truncated input file is a run measuring something
#: other than what the case says it measures.
MAX_INPUT_FILES_PER_CASE = 40
MAX_INPUT_BYTES_PER_CASE = 262_144

#: How many times the grader is re-asked after a response that will not parse.
#: One re-ask, because a strict-JSON instruction failing twice is a provider
#: fact worth recording rather than a transient worth grinding on. Every attempt
#: is written into `error.json`.
DEFAULT_GRADER_RETRIES = 1

#: Carried into every benchmark.json, verbatim, so the caveat cannot be lost
#: between this file and a reader of the artifact.
SINGLE_AGENT_LIMITATION = (
    "Every number here was produced by ONE agent model. It is one point of evidence, "
    "not a population: a delta measured on this model is a fact about this model "
    "holding these skills, and says nothing about how another model would do."
)
GRADER_BLINDING_LIMITATION = (
    "The grader is blinded by construction — it receives the same fields for both "
    "arms and is never told which arm, or that two arms exist. It is not blinded "
    "against self-identification: a response that says 'per the AST01 skill' reveals "
    "its arm, and no grader prompt can prevent that."
)
PAIRING_RULE = (
    "A case enters the summary only when BOTH arms completed. A case whose with_skill "
    "or without_skill run failed is excluded from BOTH means with its reason listed in "
    "`excluded`, because a delta computed over two different case sets is not a delta."
)

SKILL_BLOCK_BEGIN = ">>>>>>>>>> BEGIN INSTALLED SKILL: {name} <<<<<<<<<<"
SKILL_BLOCK_END = ">>>>>>>>>> END INSTALLED SKILL: {name} <<<<<<<<<<"

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

#: Longest evidence string kept from the grader, per assertion. Long enough for
#: a quote that settles the question, short enough that a grading.json stays
#: readable next to the response it grades.
MAX_EVIDENCE_CHARS = 400


class SkillEvalError(RuntimeError):
    """A harness-level failure: a malformed case, an unreadable input, a
    configuration this runner refuses to run."""


class GradingParseError(ValueError):
    """The grader answered and the answer will not bind to the case's assertions."""


# --------------------------------------------------------------------------- #
# Cases
# --------------------------------------------------------------------------- #


@dataclasses.dataclass(frozen=True)
class EvalCase:
    """One hand-authored case out of `skills/<skill>/evals/evals.json`.

    `skill` is the DIRECTORY (`AST01`); `skill_name` is the frontmatter name the
    case file declares (`ast01-malicious-skills`). Both are recorded because a
    reader of a workspace directory has only the first and a reader of the case
    file has only the second.
    """

    skill: str
    skill_name: str
    case_id: int
    prompt: str
    expected_output: str
    files: tuple[str, ...]
    assertions: tuple[str, ...]
    case_file: str = DEFAULT_CASE_FILE

    @property
    def slug(self) -> str:
        """The workspace directory name for this case, and its key in feedback.json.

        The tuned file keeps the bare `AST01-case-1` spelling it has always had.
        Any other case file inserts its own stem — `AST01-control-case-1`,
        `AST01-regression-case-1` — so a control run, a regression run and a tuned
        run can never land in the same directory, share a `feedback.json` key, or
        be averaged into one another's benchmark by a reader who assumed one
        workspace held one corpus.
        """
        stem = Path(self.case_file).stem
        infix = "" if self.case_file == DEFAULT_CASE_FILE else f"{stem}-"
        return f"{self.skill}-{infix}case-{self.case_id}"

    @property
    def skill_md(self) -> Path:
        return SKILLS_DIR / self.skill / "SKILL.md"


def discover_cases(
    skills: list[str] | None = None,
    case_ids: list[int] | None = None,
    skills_dir: Path = SKILLS_DIR,
    case_file: str = DEFAULT_CASE_FILE,
) -> list[EvalCase]:
    """Every authored case, filtered by `--skills` / `--cases`.

    Discovered from disk rather than from a list held here: a skill that adds
    cases is run the moment the file lands. A `--skills` entry that matches no
    directory raises rather than quietly running fewer cases than asked for.

    `case_file` selects WHICH authored set to run. It defaults to the tuned
    `evals.json`; `CONTROL_CASE_FILE` is the blind control, one case per skill,
    and the whole reason it can be trusted is that nothing consults it while a
    `SKILL.md` is being edited. `REGRESSION_CASE_FILE` is the corpus that used to
    be that control and is now a regression suite. Running either is a separate,
    deliberate act, which is why it is a flag and not a merge.
    """
    available = sorted(d.name for d in skills_dir.iterdir() if (d / "evals" / case_file).is_file())
    wanted = list(available)
    if skills:
        unknown = [s for s in skills if s not in available]
        if unknown:
            raise SkillEvalError(f"--skills names {unknown} which ship no evals/{case_file}; have {available}")
        wanted = [s for s in available if s in skills]

    cases: list[EvalCase] = []
    for skill in wanted:
        payload = json.loads((skills_dir / skill / "evals" / case_file).read_text(encoding="utf-8"))
        for raw in payload.get("evals", []):
            if case_ids is not None and raw["id"] not in case_ids:
                continue
            cases.append(
                EvalCase(
                    skill=skill,
                    skill_name=payload["skill_name"],
                    case_id=int(raw["id"]),
                    prompt=raw["prompt"],
                    expected_output=raw["expected_output"],
                    files=tuple(raw.get("files", [])),
                    assertions=tuple(raw["assertions"]),
                    case_file=case_file,
                )
            )
    return cases


# --------------------------------------------------------------------------- #
# Prompts — the whole counterfactual lives here
# --------------------------------------------------------------------------- #

AGENT_PREAMBLE = (
    "You are an AI agent answering one request from a colleague.\n\n"
    "This session has NO tool access and NO filesystem access. Everything you are "
    "permitted to rely on appears below; if something is not below, you do not have it. "
    "Answer the request directly, completely, and in your own words."
)

AGENT_CLOSING = "Write your complete answer now. It is the only thing the colleague will see."


def _read_text_file(path: Path) -> str:
    """A file's text, or an honest placeholder when it is not text.

    `fixtures/AST08/` ships real `.pyc` bytes on purpose (see `.gitignore`), so
    "this input is binary" is a state a case can legitimately reach. It is
    recorded as such, identically in both arms, rather than decoded with
    `errors="replace"` into something that looks like content.
    """
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"[binary file: {path.stat().st_size} bytes, not reproducible as text]"


def _expand_inputs(case: EvalCase, repo: Path = REPO) -> list[tuple[str, str]]:
    """`(repo-relative path, contents)` for every input file the case names.

    A `files` entry may name a directory — several cases hand the agent a whole
    fixture package — in which case every file beneath it is inlined, sorted, so
    the ordering is a property of the paths and not of the filesystem.
    """
    collected: list[Path] = []
    for rel in case.files:
        target = repo / rel
        if not target.exists():
            raise SkillEvalError(f"{case.slug}: input {rel!r} does not exist")
        if target.is_dir():
            collected.extend(sorted(p for p in target.rglob("*") if p.is_file()))
        else:
            collected.append(target)

    if len(collected) > MAX_INPUT_FILES_PER_CASE:
        raise SkillEvalError(f"{case.slug}: {len(collected)} input files exceeds the {MAX_INPUT_FILES_PER_CASE} cap")
    total = sum(p.stat().st_size for p in collected)
    if total > MAX_INPUT_BYTES_PER_CASE:
        raise SkillEvalError(f"{case.slug}: {total} bytes of input exceeds the {MAX_INPUT_BYTES_PER_CASE} cap")

    return [(p.relative_to(repo).as_posix(), _read_text_file(p)) for p in collected]


def files_section(case: EvalCase, repo: Path = REPO) -> str | None:
    """The attached-files block, or None when the case attaches none."""
    inputs = _expand_inputs(case, repo)
    if not inputs:
        return None
    parts = [
        "The following files are attached to the request. Their contents are reproduced "
        "in full and are the only version of them you have."
    ]
    for rel, text in inputs:
        parts.append(f"--- BEGIN FILE: {rel} ---\n{text}\n--- END FILE: {rel} ---")
    return "\n\n".join(parts)


def skill_section(case: EvalCase) -> str:
    """The installed-skill block: the `SKILL.md` verbatim, framed as instructions.

    Verbatim includes the YAML frontmatter, because that is what a runtime hands
    an agent — trimming it here would make the with_skill arm a test of an
    edited skill rather than of the shipped one.
    """
    content = case.skill_md.read_text(encoding="utf-8")
    return (
        f"{SKILL_BLOCK_BEGIN.format(name=case.skill_name)}\n"
        "The skill below is installed in this session. Treat it as your operating "
        "instructions for this request: follow its decision rules, use its vocabulary, "
        "and respect the limits it states about what it can and cannot decide.\n\n"
        f"{content}\n"
        f"{SKILL_BLOCK_END.format(name=case.skill_name)}"
    )


def agent_prompt_sections(case: EvalCase, *, with_skill: bool, repo: Path = REPO) -> list[str]:
    """The agent prompt as an ordered list of sections.

    THIS is where the counterfactual is enforced. The two arms call one function
    with one flag, and the flag inserts or omits exactly one element of the
    returned list. Nothing else in the list can differ, because nothing else
    reads the flag.
    """
    sections = [AGENT_PREAMBLE]
    if with_skill:
        sections.append(skill_section(case))
    sections.append(f"--- BEGIN REQUEST ---\n{case.prompt}\n--- END REQUEST ---")
    attached = files_section(case, repo)
    if attached is not None:
        sections.append(attached)
    sections.append(AGENT_CLOSING)
    return sections


def build_agent_prompt(case: EvalCase, *, with_skill: bool, repo: Path = REPO) -> str:
    return "\n\n".join(agent_prompt_sections(case, with_skill=with_skill, repo=repo))


GRADER_INSTRUCTIONS = """You are grading one response against a fixed checklist of assertions.

You are told nothing about how the response was produced, and you must not speculate
about it. Grade only what the response says.

Rules:
1. Judge each assertion INDEPENDENTLY and in order. An assertion the response simply
   does not address is FAILED, not passed — absence is never satisfaction.
2. "passed": true only when the response actually does what the assertion states.
   Close is not passed. Implied is not passed.
3. "evidence": a short quote from the response that settles it, or a plain statement
   that the response contains nothing addressing the assertion. Under 300 characters.
4. Do not reward length, confidence or formatting. A short response that satisfies an
   assertion passes it; a long one that does not, fails it.

The reference answer is background describing what a good response would contain. The
ASSERTIONS are the checklist. Where they disagree, grade the assertions.

Reply with ONE JSON object and nothing else — no prose before it, no code fence:

{"assertion_results": [{"index": 1, "passed": true, "evidence": "..."}]}

It must contain exactly ASSERTION_COUNT entries, with "index" running 1..ASSERTION_COUNT
in that order, one per assertion below."""


def build_grading_prompt(case: EvalCase, response: str) -> str:
    """The grader's prompt. Carries no arm label and no skill content.

    Both omissions are load-bearing: the grader must not be able to tell a
    with_skill response from a without_skill one, and it must not be handed the
    skill whose value is under measurement — a grader reading the skill would
    grade against the skill's own framing instead of the authored assertions.
    """
    numbered = "\n".join(f"{i}. {text}" for i, text in enumerate(case.assertions, start=1))
    instructions = GRADER_INSTRUCTIONS.replace("ASSERTION_COUNT", str(len(case.assertions)))
    return (
        f"{instructions}\n\n"
        f"--- BEGIN REQUEST THAT WAS ANSWERED ---\n{case.prompt}\n--- END REQUEST THAT WAS ANSWERED ---\n\n"
        f"--- BEGIN REFERENCE ANSWER (background) ---\n{case.expected_output}\n"
        f"--- END REFERENCE ANSWER (background) ---\n\n"
        f"--- BEGIN RESPONSE UNDER GRADING ---\n{response}\n--- END RESPONSE UNDER GRADING ---\n\n"
        f"--- BEGIN ASSERTIONS ---\n{numbered}\n--- END ASSERTIONS ---"
    )


def parse_grading(raw: str, case: EvalCase) -> list[dict[str, Any]]:
    """The grader's raw text -> one result per assertion, in the case's order.

    The assertion TEXT is taken from the case, never from the grader. A grader
    that paraphrases an assertion while marking it passed would otherwise
    rewrite the thing it was supposed to check, and the artifact would record
    the paraphrase as the checklist.

    Raises GradingParseError on anything that will not bind: no JSON object, no
    `assertion_results`, the wrong number of entries, a duplicated or missing
    index, a non-boolean verdict. A grading that will not bind is a refusal, and
    a refusal is recorded — never coerced into a pass or a fail.
    """
    match = _JSON_OBJECT_RE.search(raw or "")
    if not match:
        raise GradingParseError("no JSON object in the grader response")
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise GradingParseError(f"grader response is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise GradingParseError("grader response is not a JSON object")

    entries = payload.get("assertion_results")
    if not isinstance(entries, list):
        raise GradingParseError("grader response has no `assertion_results` list")
    if len(entries) != len(case.assertions):
        raise GradingParseError(f"grader returned {len(entries)} result(s) for {len(case.assertions)} assertion(s)")

    by_index: dict[int, dict[str, Any]] = {}
    for position, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise GradingParseError(f"assertion_results[{position - 1}] is not an object")
        index = entry.get("index", position)
        try:
            index = int(index)
        except (TypeError, ValueError) as exc:
            raise GradingParseError(f"assertion_results[{position - 1}] has non-integer index {index!r}") from exc
        if not 1 <= index <= len(case.assertions):
            raise GradingParseError(f"index {index} is outside 1..{len(case.assertions)}")
        if index in by_index:
            raise GradingParseError(f"index {index} appears twice")
        passed = entry.get("passed")
        if not isinstance(passed, bool):
            raise GradingParseError(f"index {index}: `passed` is {passed!r}, not a boolean")
        evidence = str(entry.get("evidence", "")).strip()
        by_index[index] = {
            "text": case.assertions[index - 1],
            "passed": passed,
            "evidence": evidence[:MAX_EVIDENCE_CHARS],
        }

    missing = sorted(set(range(1, len(case.assertions) + 1)) - set(by_index))
    if missing:
        raise GradingParseError(f"no result for assertion index(es) {missing}")
    return [by_index[i] for i in range(1, len(case.assertions) + 1)]


def summarise(assertion_results: list[dict[str, Any]]) -> dict[str, Any]:
    """`{"passed", "failed", "total", "pass_rate"}` — every field re-derivable
    from `assertion_results` by anyone holding the same file."""
    total = len(assertion_results)
    passed = sum(1 for r in assertion_results if r["passed"])
    return {
        "passed": passed,
        "failed": total - passed,
        "total": total,
        "pass_rate": round(passed / total, 4) if total else 0.0,
    }


# --------------------------------------------------------------------------- #
# Adapters
# --------------------------------------------------------------------------- #


def build_adapter(spec: str) -> ProviderAdapter:
    """One of the verified models, as a live adapter. No new transports here."""
    if spec not in VERIFIED_MODELS:
        raise SkillEvalError(f"{spec!r} is not on the verified roster; choose one of {list(VERIFIED_MODELS)}")
    provider, _, model = spec.partition("/")
    if provider == "bedrock":
        return BedrockAdapter(model=model)
    if provider == "claude-cli":
        return ClaudeCliAdapter(model=model)
    if provider == "anthropic-compatible":
        return AnthropicCompatibleAdapter(model=model, api_key=_zai_key())
    raise SkillEvalError(f"no adapter for provider {provider!r}")  # pragma: no cover - guarded by VERIFIED_MODELS


def _usage_dict(usage: TokenUsage | None, provider: str) -> tuple[int | None, dict[str, Any]]:
    """`(total_tokens, detail)` for a timing.json.

    `total_tokens` is null — never zero, never estimated — when the provider
    reported nothing, and `detail.token_source` says which provider declined to
    report it. A zero would read as a call that cost nothing.
    """
    if usage is None:
        return None, {
            "token_source": f"{provider} reports no token usage; total_tokens is null, not zero",
            "input_tokens": None,
            "output_tokens": None,
        }
    return usage.total_tokens, {
        "token_source": usage.source,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
    }


# --------------------------------------------------------------------------- #
# Running one (case, configuration)
# --------------------------------------------------------------------------- #


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def is_complete(config_dir: Path, *, require_grading: bool = True) -> bool:
    """Has this (case, configuration) already produced a usable result?

    True only when a response, a `timing.json` and — unless `--no-grade` is in
    force — a parseable `grading.json` all exist. An `error.json` is not
    completion: a resumed run retries it, which is the behaviour a long
    interrupted run needs.

    `require_grading=False` is what `--no-grade` resumes against, where grading
    is the sibling module's job and its absence is expected rather than a gap.
    """
    if not (config_dir / "outputs" / "response.md").is_file():
        return False
    if not (config_dir / "timing.json").is_file():
        return False
    if not require_grading:
        return True
    grading = config_dir / "grading.json"
    if not grading.is_file():
        return False
    try:
        payload = json.loads(grading.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return isinstance(payload.get("summary"), dict) and isinstance(payload.get("assertion_results"), list)


def run_configuration(
    case: EvalCase,
    configuration: str,
    config_dir: Path,
    agent: ProviderAdapter,
    grader: ProviderAdapter | None,
    *,
    grader_retries: int = DEFAULT_GRADER_RETRIES,
    repo: Path = REPO,
) -> dict[str, Any]:
    """Run one arm of one case and write its artifacts. Never raises for a
    provider failure — it records one and returns `{"ok": False, ...}`.

    `grader=None` (`--no-grade`) runs the agent and stops: `outputs/`,
    `timing.json`, `run.json` and `prompt.txt` are written and grading is left to
    `eval/skill_eval_grade.py`, whose blind grader owns `grading.json`,
    `benchmark.json` and `assertion-review.json` in the composed pipeline.
    """
    models = {"agent": agent.name}
    if grader is not None:
        models["grader"] = grader.name
    config_dir.mkdir(parents=True, exist_ok=True)
    # A retry must not leave the previous attempt's grading beside a new failure.
    (config_dir / "grading.json").unlink(missing_ok=True)
    (config_dir / "error.json").unlink(missing_ok=True)

    def fail(stage: str, provider: str, error: str, attempts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        record = {
            "eval": case.slug,
            "skill": case.skill,
            "case_id": case.case_id,
            "configuration": configuration,
            "stage": stage,
            "provider": provider,
            "error": error,
            "models": models,
            "timestamp": _now(),
        }
        if attempts:
            record["attempts"] = attempts
        _write_json(config_dir / "error.json", record)
        return {"ok": False, **record}

    try:
        prompt = build_agent_prompt(case, with_skill=(configuration == "with_skill"), repo=repo)
    except SkillEvalError as exc:
        return fail("prompt", "harness", str(exc))
    (config_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

    started = time.perf_counter()
    try:
        response = agent.judge(prompt)
    except RuntimeError as exc:
        return fail("agent", agent.name, str(exc))
    agent_ms = int((time.perf_counter() - started) * 1000)
    usage = getattr(agent, "last_usage", None)

    if not (response or "").strip():
        return fail("agent", agent.name, "the agent returned an empty response")

    outputs = config_dir / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    (outputs / "response.md").write_text(response, encoding="utf-8")

    # `run.json` — the sidecar `eval/skill_eval_grade.py` reads first when it has
    # to answer "which model produced this run?". timing.json's two contract
    # fields have no room for it, and a grader that cannot name the agent cannot
    # check the rule that the two must differ. Written here because the runner is
    # the only process that knows the answer first-hand.
    _write_json(
        config_dir / "run.json",
        {
            "eval": case.slug,
            "skill": case.skill,
            "case_id": case.case_id,
            "configuration": configuration,
            "agent_model": agent.name,
            "models": models,
            "skill_content_included": configuration == "with_skill",
            "input_files": list(case.files),
            "prompt_chars": len(prompt),
            "ran_at": _now(),
        },
    )

    attempts: list[dict[str, Any]] = []
    assertion_results: list[dict[str, Any]] | None = None
    grading_ms = 0
    if grader is not None:
        grading_prompt = build_grading_prompt(case, response)
        grading_started = time.perf_counter()
        for attempt in range(1, grader_retries + 2):
            try:
                raw = grader.judge(grading_prompt)
            except RuntimeError as exc:
                attempts.append({"attempt": attempt, "error": str(exc)})
                continue
            try:
                assertion_results = parse_grading(raw, case)
                break
            except GradingParseError as exc:
                excerpt, chars = response_excerpt(raw)
                attempts.append(
                    {"attempt": attempt, "error": str(exc), "response_excerpt": excerpt, "response_chars": chars}
                )
        grading_ms = int((time.perf_counter() - grading_started) * 1000)

    total_tokens, token_detail = _usage_dict(usage, agent.name)
    timing = {
        "total_tokens": total_tokens,
        "duration_ms": agent_ms,
        "models": models,
        "measures": (
            "duration_ms and total_tokens are the AGENT call only — the cost of the arm "
            "under test. Grading is harness overhead, identical for both arms, and is "
            "recorded separately as grading_duration_ms."
        ),
        "grading_duration_ms": grading_ms,
        "response_chars": len(response),
        **token_detail,
    }
    _write_json(config_dir / "timing.json", timing)

    if grader is None:
        # --no-grade: the run happened and is on disk; grading belongs to
        # eval/skill_eval_grade.py, and reporting a pass_rate here would invent one.
        return {"ok": True, "summary": None, "duration_ms": agent_ms, "total_tokens": total_tokens}

    if assertion_results is None:
        reason = f"grader failed to return bindable JSON in {len(attempts)} attempt(s)"
        return fail("grading", grader.name, reason, attempts)

    summary = summarise(assertion_results)
    _write_json(
        config_dir / "grading.json",
        {
            "assertion_results": assertion_results,
            "summary": summary,
            "models": models,
            "eval": case.slug,
            "configuration": configuration,
            "graded_at": _now(),
            "grader_attempts": len(attempts) + 1,
        },
    )
    return {"ok": True, "summary": summary, "duration_ms": agent_ms, "total_tokens": total_tokens}


# --------------------------------------------------------------------------- #
# benchmark.json / feedback.json — recomputed from the workspace, never from RAM
# --------------------------------------------------------------------------- #


def _stats(values: list[float | None], ndigits: int) -> dict[str, Any]:
    """`{"n", "mean", "stddev"}` over the values that exist.

    A missing value (a provider that reported no token count) is EXCLUDED and
    the surviving count is published as `n`, so a mean over three of five runs
    says so. All-missing renders as `n: 0` with null mean and null stddev —
    never 0.0, which would read as a measurement.

    ONE surviving value renders as `stddev: null` for the same reason, and this
    is the one place where the two modules that write `benchmark.json` had
    disagreed: this function published `0.0` while
    `eval/skill_eval_grade.py::_summarise` published `null`, so the same
    situation read as "we measured no spread" in one iteration directory and
    "one observation has no spread" in the next. `null` is the true statement
    and it is now the only one either module writes — `STDDEV_NOTE` says so
    inside every artifact both of them produce.
    """
    present = [float(v) for v in values if v is not None]
    if not present:
        return {"n": 0, "mean": None, "stddev": None}
    mean = round(statistics.fmean(present), ndigits)
    stddev = round(statistics.stdev(present), ndigits) if len(present) > 1 else None
    return {"n": len(present), "mean": mean, "stddev": stddev}


def _delta(with_block: dict[str, Any], without_block: dict[str, Any], ndigits: int) -> float | None:
    """with_skill minus without_skill, from the ROUNDED means so a reader
    holding the two published numbers reproduces the published delta exactly."""
    a, b = with_block.get("mean"), without_block.get("mean")
    if a is None or b is None:
        return None
    return round(a - b, ndigits)


def read_configuration(config_dir: Path) -> dict[str, Any]:
    """What one arm's directory says about itself: complete, errored or absent."""
    if not config_dir.is_dir():
        return {"status": "absent", "reason": "no directory — not run"}
    error_path = config_dir / "error.json"
    if error_path.is_file():
        record = json.loads(error_path.read_text(encoding="utf-8"))
        return {
            "status": "error",
            "reason": f"{record.get('stage', 'unknown')} stage failed on "
            f"{record.get('provider', 'unknown')}: {record.get('error', '')}",
        }
    if not is_complete(config_dir):
        return {"status": "incomplete", "reason": "no parseable grading.json — the run did not finish"}
    grading = json.loads((config_dir / "grading.json").read_text(encoding="utf-8"))
    timing = json.loads((config_dir / "timing.json").read_text(encoding="utf-8"))
    return {
        "status": "complete",
        "pass_rate": grading["summary"]["pass_rate"],
        "passed": grading["summary"]["passed"],
        "total": grading["summary"]["total"],
        "time_seconds": round(timing["duration_ms"] / 1000, 3),
        "tokens": timing.get("total_tokens"),
    }


def build_benchmark(iteration_dir: Path, models: dict[str, str], iteration: int) -> dict[str, Any]:
    """`benchmark.json`, recomputed from the directories on disk.

    From disk and not from the run's own memory, so a resumed run's summary
    covers the cases an earlier process completed, and so `--benchmark-only` can
    reproduce any published figure from an archived workspace.
    """
    slugs = sorted(d.name for d in iteration_dir.iterdir() if d.is_dir())
    cases: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for slug in slugs:
        arms = {cfg: read_configuration(iteration_dir / slug / cfg) for cfg in CONFIGURATIONS}
        broken = [cfg for cfg, arm in arms.items() if arm["status"] != "complete"]
        if broken:
            for cfg in broken:
                excluded.append({"eval": slug, "configuration": cfg, "reason": arms[cfg]["reason"]})
            continue
        row = {"eval": slug, **{cfg: arms[cfg] for cfg in CONFIGURATIONS}}
        row["pass_rate_delta"] = round(arms["with_skill"]["pass_rate"] - arms["without_skill"]["pass_rate"], 4)
        cases.append(row)

    summary: dict[str, Any] = {}
    for cfg in CONFIGURATIONS:
        summary[cfg] = {
            "pass_rate": _stats([c[cfg]["pass_rate"] for c in cases], 4),
            "time_seconds": _stats([c[cfg]["time_seconds"] for c in cases], 2),
            "tokens": _stats([c[cfg]["tokens"] for c in cases], 1),
        }
    summary["delta"] = {
        "pass_rate": _delta(summary["with_skill"]["pass_rate"], summary["without_skill"]["pass_rate"], 4),
        "time_seconds": _delta(summary["with_skill"]["time_seconds"], summary["without_skill"]["time_seconds"], 2),
        "tokens": _delta(summary["with_skill"]["tokens"], summary["without_skill"]["tokens"], 1),
    }

    return {
        "generated_by": "eval/skill_evals.py",
        "generated_at": _now(),
        "iteration": iteration,
        "models": models,
        "measures": (
            "pass_rate is the fraction of a case's hand-authored assertions the graded "
            "response satisfied. It is NOT a detector F1 and NOT a judge rubric total; "
            "nothing here is averaged with either surface."
        ),
        "counts": {
            "cases_in_workspace": len(slugs),
            "cases_paired": len(cases),
            "cases_excluded": len(slugs) - len(cases),
        },
        "excluded": excluded,
        "cases": cases,
        "run_summary": summary,
        "notes": {"stddev": STDDEV_NOTE},
        "limitations": [SINGLE_AGENT_LIMITATION, GRADER_BLINDING_LIMITATION, PAIRING_RULE],
    }


def write_feedback(iteration_dir: Path, slugs: list[str]) -> dict[str, str]:
    """`feedback.json`: one key per eval slug, an empty string for a human note.

    Merged, never overwritten. A note a human wrote after the first pass of an
    interrupted run survives the resume that completes it.
    """
    path = iteration_dir / "feedback.json"
    existing: dict[str, str] = {}
    if path.is_file():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            existing = {str(k): str(v) for k, v in loaded.items()}
    merged = {slug: existing.get(slug, "") for slug in sorted(set(slugs) | set(existing))}
    _write_json(path, merged)
    return merged


# --------------------------------------------------------------------------- #
# Iterations
# --------------------------------------------------------------------------- #

_ITERATION_RE = re.compile(r"^iteration-(\d+)$")


def existing_iterations(workspace: Path) -> list[int]:
    if not workspace.is_dir():
        return []
    return sorted(int(m.group(1)) for d in workspace.iterdir() if d.is_dir() and (m := _ITERATION_RE.match(d.name)))


def next_iteration(workspace: Path) -> int:
    """The next UNUSED integer. A rerun never writes into a directory that
    already holds a corpus; resuming one is opt-in via `--iteration`."""
    found = existing_iterations(workspace)
    return (max(found) + 1) if found else 1


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _parse_csv_ints(raw: str) -> list[int] | None:
    if not raw.strip():
        return None
    return [int(part) for part in raw.split(",") if part.strip()]


def _parse_csv(raw: str) -> list[str] | None:
    if not raw.strip():
        return None
    return [part.strip() for part in raw.split(",") if part.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eval/skill_evals.py",
        description="Run every skills/*/evals/evals.json case with and without its skill.",
    )
    parser.add_argument("--iteration", type=int, default=None, help="resume/target iteration-N (default: next unused)")
    parser.add_argument("--skills", default="", help="comma-separated subset, e.g. AST01,AST04")
    parser.add_argument("--cases", default="", help="comma-separated case ids, e.g. 1,2")
    parser.add_argument("--dry-run", action="store_true", help="print the plan and the roster; write nothing")
    parser.add_argument("--no-resume", action="store_true", help="re-run configurations that already completed")
    parser.add_argument("--benchmark-only", action="store_true", help="recompute benchmark.json from disk; no calls")
    parser.add_argument("--agent-model", default=DEFAULT_AGENT_MODEL, choices=VERIFIED_MODELS)
    parser.add_argument("--grader-model", default=DEFAULT_GRADER_MODEL, choices=VERIFIED_MODELS)
    parser.add_argument("--grader-retries", type=int, default=DEFAULT_GRADER_RETRIES)
    parser.add_argument(
        "--no-grade",
        action="store_true",
        help=(
            "run both arms and stop: write outputs/, timing.json, run.json and prompt.txt "
            "and leave grading.json/benchmark.json to eval/skill_eval_grade.py"
        ),
    )
    parser.add_argument("--workspace", default=str(WORKSPACE_ROOT), help="workspace root (default: %(default)s)")
    parser.add_argument(
        "--case-file",
        default=DEFAULT_CASE_FILE,
        choices=CASE_FILES,
        help=(
            "which authored corpus to run: the tuned %(default)s, control.json — the "
            "blind control that says whether a skill edit generalised — or regression.json, "
            "the spent control kept as a regression suite. Every non-default corpus gets its "
            "own run slugs, so no two ever share a workspace directory."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workspace = Path(args.workspace)

    # Only meaningful when this process grades. Under --no-grade there is no
    # grader here at all, and the same check is the sibling grader's to make.
    if not args.no_grade and args.agent_model == args.grader_model:
        print(
            f"FATAL: agent and grader are both {args.agent_model}. A model grading its own "
            "output is the failure mode this surface exists to avoid.",
            file=sys.stderr,
        )
        return 2

    models = {"agent": args.agent_model}
    if not args.no_grade:
        models["grader"] = args.grader_model

    try:
        cases = discover_cases(_parse_csv(args.skills), _parse_csv_ints(args.cases), case_file=args.case_file)
    except SkillEvalError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 2
    if not cases:
        print("FATAL: no cases matched the filters", file=sys.stderr)
        return 2

    iteration = args.iteration if args.iteration is not None else next_iteration(workspace)
    iteration_dir = workspace / f"iteration-{iteration}"

    if args.benchmark_only:
        if not iteration_dir.is_dir():
            print(f"FATAL: {iteration_dir} does not exist", file=sys.stderr)
            return 2
        benchmark = build_benchmark(iteration_dir, models, iteration)
        _write_json(iteration_dir / "benchmark.json", benchmark)
        print(f"{iteration_dir / 'benchmark.json'}: rewritten from disk")
        _print_summary(benchmark)
        return 0

    agent = build_adapter(args.agent_model)
    agent_status = agent.check_availability()
    grader = None if args.no_grade else build_adapter(args.grader_model)
    grader_status = None if grader is None else grader.check_availability()

    print(f"agent under test : {agent.name} — {'available' if agent_status.available else agent_status.reason}")
    if grader is None:
        print("grader           : none (--no-grade) — grading belongs to eval/skill_eval_grade.py")
    else:
        print(f"grader           : {grader.name} — {'available' if grader_status.available else grader_status.reason}")
    print(f"workspace        : {iteration_dir}")
    print(f"cases            : {len(cases)} × {len(CONFIGURATIONS)} configurations = {len(cases) * 2} runs")

    if args.dry_run:
        print("\nplan (nothing written, no model called):")
        for case in cases:
            with_len = len(build_agent_prompt(case, with_skill=True))
            without_len = len(build_agent_prompt(case, with_skill=False))
            print(
                f"  {case.slug:<18} {len(case.assertions)} assertions, "
                f"{len(case.files)} input path(s), prompt {without_len} -> {with_len} chars "
                f"(+{with_len - without_len} skill)"
            )
        stale = [n for n in existing_iterations(workspace) if not _iteration_is_complete(workspace, n, cases)]
        if args.iteration is None and stale:
            print(f"\nnote: iteration(s) {stale} exist and are incomplete; --iteration N resumes one.")
        return 0

    unavailable = [s for s in (agent_status, grader_status) if s is not None and not s.available]
    if unavailable:
        for status in unavailable:
            print(f"FATAL: {status.name} is unavailable: {status.reason}", file=sys.stderr)
        return 2

    iteration_dir.mkdir(parents=True, exist_ok=True)
    ran = skipped = failed = 0
    for case in cases:
        for configuration in CONFIGURATIONS:
            config_dir = iteration_dir / case.slug / configuration
            if not args.no_resume and is_complete(config_dir, require_grading=grader is not None):
                skipped += 1
                print(f"  {case.slug:<18} {configuration:<14} already complete — skipped")
                continue
            outcome = run_configuration(
                case, configuration, config_dir, agent, grader, grader_retries=args.grader_retries
            )
            ran += 1
            if outcome["ok"] and outcome["summary"] is None:
                print(
                    f"  {case.slug:<18} {configuration:<14} ran (ungraded), "
                    f"{outcome['duration_ms'] / 1000:.1f}s, {outcome['total_tokens']} tokens"
                )
            elif outcome["ok"]:
                summary = outcome["summary"]
                print(
                    f"  {case.slug:<18} {configuration:<14} "
                    f"{summary['passed']}/{summary['total']} assertions "
                    f"({summary['pass_rate']:.2f}), {outcome['duration_ms'] / 1000:.1f}s, "
                    f"{outcome['total_tokens']} tokens"
                )
            else:
                failed += 1
                print(f"  {case.slug:<18} {configuration:<14} FAILED at {outcome['stage']}: {outcome['error']}")

    print(f"\n{ran} run(s), {skipped} skipped, {failed} failed")

    if grader is None:
        # Writing a benchmark here would mean inventing pass rates nothing graded.
        print(
            "--no-grade: no grading.json, no benchmark.json. Grade and aggregate with\n"
            "  python3 eval/skill_eval_grade.py grade --grader <model>\n"
            "  python3 eval/skill_eval_grade.py aggregate"
        )
        return 0

    benchmark = build_benchmark(iteration_dir, models, iteration)
    _write_json(iteration_dir / "benchmark.json", benchmark)
    write_feedback(iteration_dir, [case.slug for case in cases])
    _print_summary(benchmark)
    return 0


def _iteration_is_complete(workspace: Path, iteration: int, cases: list[EvalCase]) -> bool:
    directory = workspace / f"iteration-{iteration}"
    return all(is_complete(directory / case.slug / cfg) for case in cases for cfg in CONFIGURATIONS)


def _fmt(value: Any) -> str:
    return "—" if value is None else f"{value}"


def _print_summary(benchmark: dict[str, Any]) -> None:
    run = benchmark["run_summary"]
    counts = benchmark["counts"]
    print(f"\n=== iteration {benchmark['iteration']} — {counts['cases_paired']} paired case(s) ===")
    print(f"  agent {benchmark['models']['agent']} · grader {benchmark['models'].get('grader', 'none')}")
    for cfg in CONFIGURATIONS:
        block = run[cfg]
        print(
            f"  {cfg:<14} pass_rate {_fmt(block['pass_rate']['mean'])} "
            f"(σ {_fmt(block['pass_rate']['stddev'])}, n={block['pass_rate']['n']})  "
            f"time {_fmt(block['time_seconds']['mean'])}s  tokens {_fmt(block['tokens']['mean'])}"
        )
    delta = run["delta"]
    print(
        f"  {'delta':<14} pass_rate {_fmt(delta['pass_rate'])}  "
        f"time {_fmt(delta['time_seconds'])}s  tokens {_fmt(delta['tokens'])}"
    )
    if counts["cases_excluded"]:
        print(f"  {counts['cases_excluded']} case(s) excluded — see benchmark.json `excluded`")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

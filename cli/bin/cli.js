#!/usr/bin/env node
// OWASP Agentic Skills Top 10 (AST01-AST10) — agent-skill CLI.
//
// Independent community reference implementation. NOT an official OWASP
// project; no OWASP endorsement, despite the repository name (see NOTICE).
//
// Commands: list, route <prompt>, audit <path>, coverage, status, help
//
// Usage:
//   node cli/bin/cli.js list
//   node cli/bin/cli.js list --tier static-detectable
//   node cli/bin/cli.js route "the scanner missed an obfuscated instruction"
//   node cli/bin/cli.js audit fixtures/AST01/V1-obfuscated-payload
//   node cli/bin/cli.js coverage
//   node cli/bin/cli.js status
//
// Zero runtime dependencies: node builtins only.
//
// Division of labour. This file reads DATA out of the repository's own
// artifacts — SKILL.md frontmatter, `scenarios/registry.yaml`'s tier lines,
// `fixtures/manifest.yaml`'s per-category counters, `config/audit.yml`'s
// provider declarations. It never re-implements a DECISION the repo already
// owns in Python: `route` and `audit` shell out to `cli/lib/bridge.py`, which
// calls `skills/advisory/scripts/triage.py` (the whitepaper's decision tree)
// and `skills/AST*/scripts/detector.py` (the detectors) directly. A second
// copy of either rule in JavaScript would be a second source of truth.
//
// Every number `coverage` prints is read from the manifests, never restated
// here; `tests/test_cli.py` re-derives them with PyYAML and fails if this
// file's readers ever disagree.

import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const REPO_ROOT = resolve(__dirname, "..", "..");

const SKILLS_DIR = join(REPO_ROOT, "skills");
const FIXTURES_DIR = join(REPO_ROOT, "fixtures");
const FIXTURE_MANIFEST = join(FIXTURES_DIR, "manifest.yaml");
const REGISTRY_PATH = join(REPO_ROOT, "scenarios", "registry.yaml");
const AUDIT_CONFIG = join(REPO_ROOT, "config", "audit.yml");
const ADAPTERS_DIR = join(REPO_ROOT, "adapters");
const BRIDGE = join(REPO_ROOT, "cli", "lib", "bridge.py");
const MARKETPLACE = join(REPO_ROOT, ".claude-plugin", "marketplace.json");
const COMMANDS_DIRS = [join(REPO_ROOT, "commands"), join(REPO_ROOT, ".claude-plugin", "commands")];
const SCORECARD_DIRS = [join(REPO_ROOT, "eval", "scorecards"), join(REPO_ROOT, "scorecards")];

const AST_IDS = Array.from({ length: 10 }, (_, i) => `AST${String(i + 1).padStart(2, "0")}`);
const ADVISORY_ID = "advisory";
const ALL_IDS = [...AST_IDS, ADVISORY_ID];
const TIERS = ["static-detectable", "agent-judgable", "out-of-artifact"];

const DISCLAIMER =
  "Independent community implementation. NOT an OWASP project; no OWASP endorsement.";

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

function readText(path) {
  try {
    return readFileSync(path, "utf-8");
  } catch {
    return null;
  }
}

function isDir(path) {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

function listDirs(path) {
  if (!isDir(path)) return [];
  return readdirSync(path, { withFileTypes: true })
    .filter((e) => e.isDirectory() && !e.name.startsWith(".") && e.name !== "__pycache__")
    .map((e) => e.name)
    .sort();
}

function unquote(value) {
  const trimmed = value.trim();
  if (trimmed.length >= 2) {
    const first = trimmed[0];
    const last = trimmed[trimmed.length - 1];
    if ((first === '"' && last === '"') || (first === "'" && last === "'")) {
      return trimmed.slice(1, -1);
    }
  }
  return trimmed;
}

function scalar(value) {
  const text = unquote(value);
  if (text === "null" || text === "~" || text === "") return null;
  if (text === "true") return true;
  if (text === "false") return false;
  if (/^-?\d+$/.test(text)) return Number(text);
  return text;
}

function oneLine(text, width = 96) {
  if (!text) return "";
  const flat = text.replace(/\s+/g, " ").trim();
  // First sentence, when the description opens with one short enough to stand
  // alone; otherwise a hard truncation. Never a silent half-sentence with no
  // marker — the ellipsis is the signal that more text exists in SKILL.md.
  const stop = flat.search(/\.\s/);
  const candidate = stop > 0 && stop + 1 <= width ? flat.slice(0, stop + 1) : flat;
  return candidate.length <= width ? candidate : `${candidate.slice(0, width - 1).trimEnd()}...`;
}

function pad(value, width) {
  const text = String(value);
  return text.length >= width ? text : text + " ".repeat(width - text.length);
}

function padStart(value, width) {
  const text = String(value);
  return text.length >= width ? text : " ".repeat(width - text.length) + text;
}

function rule(width = 78) {
  return "-".repeat(width);
}

function fail(message, code = 1) {
  console.error(`error: ${message}`);
  process.exit(code);
}

// ---------------------------------------------------------------------------
// Readers — SKILL.md frontmatter
// ---------------------------------------------------------------------------

/**
 * Top-level scalars of a SKILL.md YAML frontmatter block. Nested maps (the
 * advisory skill's `permissions:`) are skipped rather than half-parsed; the
 * CLI only needs `name` and `description`, and a partial nested parse would
 * be a quiet source of wrong output.
 */
function parseFrontmatter(text) {
  if (!text || !text.startsWith("---")) return {};
  const firstNewline = text.indexOf("\n");
  const end = text.indexOf("\n---", firstNewline);
  if (firstNewline < 0 || end < 0) return {};
  const block = text.slice(firstNewline + 1, end + 1);

  const frontmatter = {};
  let blockKey = null;
  let blockLines = [];
  for (const line of block.split("\n")) {
    if (blockKey !== null) {
      if (/^\s+\S/.test(line)) {
        blockLines.push(line.trim());
        continue;
      }
      frontmatter[blockKey] = blockLines.join(" ");
      blockKey = null;
      blockLines = [];
    }
    if (!line.trim() || line.trimStart().startsWith("#")) continue;
    if (/^\s/.test(line)) continue; // a nested key under a map — deliberately ignored
    const match = line.match(/^([A-Za-z_][\w.-]*):\s*(.*)$/);
    if (!match) continue;
    const [, key, raw] = match;
    const value = raw.trim();
    if (value === ">" || value === ">-" || value === "|" || value === "|-") {
      blockKey = key;
      blockLines = [];
      continue;
    }
    frontmatter[key] = unquote(value);
  }
  if (blockKey !== null) frontmatter[blockKey] = blockLines.join(" ");
  return frontmatter;
}

// ---------------------------------------------------------------------------
// Readers — detector modules (what a skill declares it can decide)
// ---------------------------------------------------------------------------

function pyDictBody(source, name) {
  const opener = new RegExp(`^${name}\\b[^=\\n]*=\\s*\\{`, "m");
  const match = source.match(opener);
  if (!match) return null;
  const open = source.indexOf("{", match.index);
  if (/^\{\s*\}/.test(source.slice(open))) return ""; // inline empty dict
  const close = source.indexOf("\n}", open);
  if (close < 0) return null;
  return source.slice(open + 1, close);
}

/**
 * A skill's own tier declaration: `SCENARIO_TIERS` in its detector module.
 *
 * This is the skill's claim about what IT can decide, which is what `list
 * --tier` filters on. It is NOT the whitepaper scenario tiering —
 * `scenarios/registry.yaml` is authoritative on that, and `coverage` reports
 * it. The two answer different questions and are never summed.
 */
function readDetectorDeclaration(skillDir) {
  const source = readText(join(skillDir, "scripts", "detector.py"));
  if (source === null) return { tiers: {}, detectors: [], present: false };
  const tiers = {};
  const tierBody = pyDictBody(source, "SCENARIO_TIERS");
  if (tierBody) {
    for (const line of tierBody.split("\n")) {
      // A trailing `# comment` is allowed: AST07's table annotates each
      // registry id with its whitepaper title, and dropping those entries
      // silently would under-report the category's tier counts.
      const entry = line.match(/^\s*"([^"]+)"\s*:\s*"([^"]+)"\s*,?\s*(?:#.*)?$/);
      if (entry) tiers[entry[1]] = entry[2];
    }
  }
  const detectors = [];
  const detectorBody = pyDictBody(source, "DETECTORS");
  if (detectorBody) {
    for (const line of detectorBody.split("\n")) {
      const entry = line.match(/^\s*"([^"]+)"\s*:/);
      if (entry) detectors.push(entry[1]);
    }
  }
  return { tiers, detectors, present: true };
}

// ---------------------------------------------------------------------------
// Readers — scenarios/registry.yaml (authoritative on scenario tier)
// ---------------------------------------------------------------------------

/**
 * Per-category scenario tier counts.
 *
 * A narrow, indentation-anchored scan of the one block shape the registry
 * uses (`  - id:` / `    category:` / `    tier:`) rather than a general YAML
 * parser, because this CLI ships with zero runtime dependencies.
 * `tests/test_cli.py` re-derives the same counts with PyYAML and fails on any
 * disagreement, so the shortcut cannot drift unnoticed.
 */
function readRegistry() {
  const source = readText(REGISTRY_PATH);
  if (source === null) return { scenarios: [], byCategory: new Map() };
  const scenarios = [];
  let inScenarios = false;
  let current = null;
  for (const line of source.split("\n")) {
    if (/^scenarios:\s*$/.test(line)) {
      inScenarios = true;
      continue;
    }
    if (!inScenarios) continue;
    if (/^\S/.test(line)) break; // next top-level key ends the scenarios block
    const idMatch = line.match(/^ {2}- id:\s*(\S+)\s*$/);
    if (idMatch) {
      current = { id: idMatch[1], category: null, tier: null };
      scenarios.push(current);
      continue;
    }
    if (!current) continue;
    const categoryMatch = line.match(/^ {4}category:\s*(\S+)\s*$/);
    if (categoryMatch && current.category === null) current.category = unquote(categoryMatch[1]);
    const tierMatch = line.match(/^ {4}tier:\s*(\S+)\s*$/);
    if (tierMatch && current.tier === null) current.tier = unquote(tierMatch[1]);
  }
  const byCategory = new Map();
  for (const scenario of scenarios) {
    if (!scenario.category) continue;
    const bucket = byCategory.get(scenario.category) || { total: 0 };
    bucket.total += 1;
    bucket[scenario.tier] = (bucket[scenario.tier] || 0) + 1;
    byCategory.set(scenario.category, bucket);
  }
  return { scenarios, byCategory };
}

// ---------------------------------------------------------------------------
// Readers — fixtures/manifest.yaml (F1 state and corpus counts)
// ---------------------------------------------------------------------------

function readFixtureManifest() {
  const source = readText(FIXTURE_MANIFEST);
  const categories = new Map();
  if (source === null) return categories;
  let inCategories = false;
  let current = null;
  let section = null;
  for (const line of source.split("\n")) {
    if (/^categories:\s*$/.test(line)) {
      inCategories = true;
      continue;
    }
    if (!inCategories) continue;
    if (/^\S/.test(line)) break;
    const categoryMatch = line.match(/^ {2}([A-Za-z][\w-]*):\s*$/);
    if (categoryMatch) {
      current = {
        id: categoryMatch[1],
        name: null,
        status: null,
        f1_scope: null,
        published_f1: null,
        cases: 0,
        detectable_scenarios: 0,
        registry_coverage: {},
      };
      categories.set(current.id, current);
      section = null;
      continue;
    }
    if (!current) continue;
    const keyMatch = line.match(/^ {4}([A-Za-z][\w-]*):\s*(.*)$/);
    if (keyMatch) {
      const [, key, raw] = keyMatch;
      section = key;
      const value = raw.trim();
      if (value === "" || value === "[]") continue;
      if (key in current) current[key] = scalar(value);
      continue;
    }
    const nestedKey = line.match(/^ {6}([A-Za-z][\w-]*):\s*(.*)$/);
    if (nestedKey && section === "registry_coverage") {
      current.registry_coverage[nestedKey[1]] = scalar(nestedKey[2]);
      continue;
    }
    const listItem = line.match(/^ {6}- id:\s*(\S+)\s*$/);
    if (listItem) {
      if (section === "cases") current.cases += 1;
      if (section === "detectable_scenarios") current.detectable_scenarios += 1;
    }
  }
  return categories;
}

/**
 * How a category reports F1 today, in the manifest's own vocabulary — three
 * outcomes that must never be blended: a published number,
 * `pending-detector` (a labeled corpus exists, no detector consumes it), or
 * `declared-and-uncovered` (the detectable tier is empty, so the never-pad
 * rule forbids manufacturing a number at all).
 */
function f1State(entry) {
  if (!entry) return { value: "not-in-manifest", published: false, reason: "not-in-manifest" };
  if (entry.published_f1 === null || entry.published_f1 === undefined) {
    return {
      value: String(entry.status || "declared-and-uncovered"),
      published: false,
      reason: "empty-detectable-tier",
    };
  }
  if (entry.published_f1 === "pending-detector") {
    return { value: "pending-detector", published: false, reason: "no-detector-consumes-corpus" };
  }
  return { value: String(entry.published_f1), published: true, reason: "published" };
}

// ---------------------------------------------------------------------------
// Readers — config/audit.yml + adapters/ (judge provider roster)
// ---------------------------------------------------------------------------

function readDeclaredProviders() {
  const source = readText(AUDIT_CONFIG);
  const providers = [];
  let runtimeEntries = 0;
  if (source === null) return { providers, runtimeEntries };
  let inProviders = false;
  let current = null;
  let blockKey = null;
  let blockLines = [];
  for (const line of source.split("\n")) {
    if (/^runtime_entries:\s*\[\]\s*$/.test(line)) {
      runtimeEntries = 0;
      inProviders = false;
      continue;
    }
    if (/^runtime_entries:\s*$/.test(line)) {
      inProviders = false;
      current = null;
      blockKey = null;
      continue;
    }
    if (/^providers:\s*$/.test(line)) {
      inProviders = true;
      continue;
    }
    if (!inProviders) {
      if (/^ {2}- /.test(line)) runtimeEntries += 1;
      continue;
    }
    if (blockKey !== null) {
      if (/^ {6}\S/.test(line)) {
        blockLines.push(line.trim());
        continue;
      }
      current[blockKey] = blockLines.join(" ");
      blockKey = null;
      blockLines = [];
    }
    if (/^\S/.test(line)) {
      inProviders = false;
      continue;
    }
    const nameMatch = line.match(/^ {2}([A-Za-z][\w.-]*):\s*$/);
    if (nameMatch) {
      current = { name: nameMatch[1], adapter: null, model: null, status: null, reason: "" };
      providers.push(current);
      continue;
    }
    if (!current) continue;
    const keyMatch = line.match(/^ {4}([A-Za-z][\w-]*):\s*(.*)$/);
    if (!keyMatch) continue;
    const [, key, raw] = keyMatch;
    const value = raw.trim();
    if (value === ">" || value === ">-" || value === "|" || value === "|-") {
      blockKey = key;
      blockLines = [];
      continue;
    }
    current[key] = unquote(value);
  }
  if (blockKey !== null && current) current[blockKey] = blockLines.join(" ");
  return { providers, runtimeEntries };
}

/** Model ids read out of the adapter modules so the CLI cannot drift from them. */
function readLiveAdapters() {
  const adapters = [];

  const bedrock = readText(join(ADAPTERS_DIR, "bedrock.py"));
  if (bedrock) {
    const region = (bedrock.match(/^REGION\s*=\s*"([^"]+)"/m) || [])[1] || "unknown-region";
    const body = pyDictBody(bedrock, "MODELS") || "";
    for (const line of body.split("\n")) {
      const entry = line.match(/^\s*"([^"]+)"\s*:\s*"([^"]+)"/);
      if (entry) {
        adapters.push({
          name: `bedrock/${entry[1]}`,
          target: entry[2],
          region,
          precondition: "AWS credential source",
        });
      }
    }
  }

  const claudeCli = readText(join(ADAPTERS_DIR, "claude_cli.py"));
  if (claudeCli) {
    const model = (claudeCli.match(/^DEFAULT_MODEL\s*=\s*"([^"]+)"/m) || [])[1] || "sonnet";
    adapters.push({
      name: `claude-cli/${model}`,
      target: "local `claude -p` binary",
      precondition: "claude on PATH",
    });
  }

  const anthropicCompatible = readText(join(ADAPTERS_DIR, "anthropic_compatible.py"));
  if (anthropicCompatible) {
    const model =
      (anthropicCompatible.match(/^DEFAULT_MODEL\s*=\s*"([^"]+)"/m) || [])[1] || "glm-5.2";
    const envVar =
      (anthropicCompatible.match(/^ZAI_API_KEY_ENV\s*=\s*"([^"]+)"/m) || [])[1] || "ZAI_API_KEY";
    const base =
      (anthropicCompatible.match(/^BASE_URL\s*=\s*"([^"]+)"/m) || [])[1] ||
      "api.z.ai/api/anthropic";
    adapters.push({
      name: `anthropic-compatible/${model}`,
      target: base,
      precondition: `${envVar} set`,
      envVar,
    });
  }
  return adapters;
}

/**
 * Whether each live adapter's LOCAL precondition holds.
 *
 * This mirrors what each adapter's own `check_availability()` inspects (a
 * binary on PATH, an API key, a credential source) and nothing more. It is
 * not a reachability probe, and it deliberately does not call
 * `adapters/base.py` — `build_roster()` APPENDS to `config/audit.yml`, and a
 * read-only status command must not write to the audit trail.
 */
function probeAdapter(adapter) {
  if (adapter.name.startsWith("claude-cli/")) {
    const found = whichSync("claude");
    return found
      ? { configured: true, detail: `claude found at ${found}` }
      : { configured: false, detail: "claude CLI not found on PATH" };
  }
  if (adapter.envVar) {
    return process.env[adapter.envVar]
      ? { configured: true, detail: `${adapter.envVar} set` }
      : { configured: false, detail: `${adapter.envVar} unset` };
  }
  if (adapter.name.startsWith("bedrock/")) {
    if (process.env.AWS_ACCESS_KEY_ID || process.env.AWS_SESSION_TOKEN) {
      return { configured: true, detail: "AWS credentials in the environment" };
    }
    if (process.env.AWS_PROFILE) {
      return { configured: true, detail: `AWS_PROFILE=${process.env.AWS_PROFILE}` };
    }
    const shared = join(homedir(), ".aws", "credentials");
    const config = join(homedir(), ".aws", "config");
    if (existsSync(shared) || existsSync(config)) {
      return { configured: true, detail: "~/.aws credential file present" };
    }
    return { configured: false, detail: "no AWS credential source found" };
  }
  return { configured: false, detail: "no precondition check for this adapter" };
}

function whichSync(binary) {
  const pathEnv = process.env.PATH || "";
  for (const entry of pathEnv.split(":")) {
    if (!entry) continue;
    const candidate = join(entry, binary);
    if (existsSync(candidate)) return candidate;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Skill discovery
// ---------------------------------------------------------------------------

function discoverSkills() {
  const manifest = readFixtureManifest();
  const registry = readRegistry();
  const skills = [];
  for (const id of ALL_IDS) {
    const dir = join(SKILLS_DIR, id);
    const skillMd = readText(join(dir, "SKILL.md"));
    if (skillMd === null) continue;
    const frontmatter = parseFrontmatter(skillMd);
    const declaration = readDetectorDeclaration(dir);
    const tierCounts = {};
    for (const tier of TIERS) {
      tierCounts[tier] = Object.values(declaration.tiers).filter((t) => t === tier).length;
    }
    const entry = manifest.get(id);
    skills.push({
      id,
      isDetector: id !== ADVISORY_ID,
      name: frontmatter.name || id,
      description: frontmatter.description || "",
      categoryName: entry ? entry.name : null,
      dir,
      tiers: declaration.tiers,
      tierCounts,
      detectors: declaration.detectors,
      hasDetector: declaration.present,
      hasCoverageMatrix: existsSync(join(dir, "coverage-matrix.md")),
      hasUsf: existsSync(join(dir, "skill.usf.yaml")),
      registry: registry.byCategory.get(id) || null,
      f1: id === ADVISORY_ID ? null : f1State(entry),
    });
  }
  return skills;
}

// ---------------------------------------------------------------------------
// Python bridge — route and audit delegate their decisions
// ---------------------------------------------------------------------------

function runBridge(args) {
  const python = process.env.AST10_PYTHON || process.env.PYTHON || "python3";
  const result = spawnSync(python, [BRIDGE, ...args], {
    encoding: "utf-8",
    maxBuffer: 32 * 1024 * 1024,
  });
  if (result.error) {
    if (result.error.code === "ENOENT") {
      fail(
        `${python} not found. \`route\` and \`audit\` delegate to cli/lib/bridge.py so the ` +
          "decision tree and the detectors are never duplicated in JavaScript. " +
          "Set AST10_PYTHON to your interpreter.",
        2
      );
    }
    fail(`${python}: ${result.error.message}`, 2);
  }
  let payload;
  try {
    payload = JSON.parse(result.stdout);
  } catch {
    const stderr = (result.stderr || "").trim();
    fail(`cli/lib/bridge.py produced no JSON${stderr ? `:\n${stderr}` : ""}`, 2);
  }
  if (payload && payload.error) fail(payload.error, 2);
  return payload;
}

// ---------------------------------------------------------------------------
// Command: list
// ---------------------------------------------------------------------------

function cmdList(options) {
  let skills = discoverSkills();
  if (options.tier) {
    if (!TIERS.includes(options.tier)) {
      fail(`unknown tier ${options.tier}; choose one of ${TIERS.join(", ")}`);
    }
    skills = skills.filter((s) => (s.tierCounts[options.tier] || 0) > 0);
  }

  if (options.json) {
    console.log(
      JSON.stringify(
        skills.map((s) => ({
          id: s.id,
          name: s.name,
          description: oneLine(s.description),
          tier_counts: s.tierCounts,
          declared_scenarios: s.tiers,
          detectors: s.detectors,
          f1: s.f1 ? s.f1.value : "not-scored-on-f1",
        })),
        null,
        2
      )
    );
    return 0;
  }

  const heading = options.tier
    ? `OWASP AST skills that decide ${options.tier} scenarios (${skills.length})`
    : `OWASP Agentic Skills Top 10 — ${skills.length} skills`;
  console.log(`\n${heading}`);
  console.log(DISCLAIMER);
  console.log(rule());
  if (skills.length === 0) {
    console.log("  (none)");
    return 0;
  }
  const nameWidth = Math.max(...skills.map((s) => s.name.length));
  for (const skill of skills) {
    const badge = skill.isDetector
      ? TIERS.filter((t) => skill.tierCounts[t] > 0)
          .map((t) => `${t} x${skill.tierCounts[t]}`)
          .join(", ") || "no scenarios declared"
      : "router — guidance-quality judged, never an F1 signal";
    console.log(`  ${pad(skill.id, 9)}${pad(skill.name, nameWidth + 2)}[${badge}]`);
    console.log(`  ${" ".repeat(9)}${oneLine(skill.description)}`);
  }
  console.log("");
  console.log(
    "Tier = what the skill's own detector module declares it can decide " +
      "(SCENARIO_TIERS)."
  );
  console.log(
    "The whitepaper's per-scenario tiering is a different question: " +
      "`coverage` reports it from scenarios/registry.yaml."
  );
  if (!options.tier) {
    const advisory = skills.find((s) => !s.isDetector);
    if (advisory) {
      console.log(
        `${advisory.name} declares no scenarios and is excluded from every --tier filter.`
      );
    }
  }
  return 0;
}

// ---------------------------------------------------------------------------
// Command: route
// ---------------------------------------------------------------------------

function cmdRoute(prompt, options) {
  if (!prompt || !prompt.trim()) {
    fail('route needs a finding, e.g. route "the scanner missed an obfuscated instruction"');
  }
  const payload = runBridge(["route", prompt]);
  if (options.json) {
    console.log(JSON.stringify(payload, null, 2));
    return 0;
  }

  console.log(`\nFinding: ${JSON.stringify(payload.finding)}`);
  console.log(rule());
  if (!payload.ast_id) {
    console.log("Primary category: none — no decision-tree branch matched");
    console.log(`Guidance:         ${payload.guidance}`);
    console.log("\nDecision owner:   skills/advisory/scripts/triage.py");
    return 0;
  }

  const primary = payload.matches[0];
  // `basis` already says "extended rule — ..." for the six categories the
  // whitepaper's tree does not number; only the four literal branches need
  // the branch number prefixed.
  const branchLabel = primary.branch
    ? `decision-tree branch ${primary.branch} — ${primary.basis}`
    : primary.basis;
  console.log(`Primary category: ${payload.ast_id} — ${payload.category}`);
  console.log(`Matched rule:     ${branchLabel}`);
  console.log(`Matched phrase:   ${JSON.stringify(payload.matched_phrase)}`);
  if (primary) {
    console.log(
      `Rule order:       ${primary.rule_order} of ${payload.total_rules}` +
        " (whitepaper branches 1-4 first, then the six extended categories)"
    );
  }
  console.log("");
  console.log("Contributing control failures (branch 5 — recorded, never a second primary):");
  const contributing = payload.matches.slice(1);
  if (contributing.length === 0) {
    console.log("  (none)");
  } else {
    for (const match of contributing) {
      const label = match.branch ? `branch ${match.branch}` : "extended rule";
      console.log(
        `  ${pad(match.ast_id, 8)}${pad(match.category, 34)}${label}, matched ${JSON.stringify(match.matched_phrase)}`
      );
    }
  }
  console.log("");
  console.log("Guidance:");
  for (const line of wrap(payload.guidance, 74)) console.log(`  ${line}`);
  console.log("");
  console.log(`Decision owner:   ${payload.source} (the whitepaper's own decision tree)`);
  console.log(
    "Not an F1 signal: the advisory router is judged on guidance quality, never detection accuracy."
  );
  return 0;
}

function wrap(text, width) {
  const words = String(text || "").split(/\s+/).filter(Boolean);
  const lines = [];
  let line = "";
  for (const word of words) {
    if (line && line.length + 1 + word.length > width) {
      lines.push(line);
      line = word;
    } else {
      line = line ? `${line} ${word}` : word;
    }
  }
  if (line) lines.push(line);
  return lines;
}

// ---------------------------------------------------------------------------
// Command: audit
// ---------------------------------------------------------------------------

function cmdAudit(target, options) {
  if (!target) fail("audit needs a path to a candidate skill package");
  const payload = runBridge(["audit", target]);
  if (options.json) {
    console.log(JSON.stringify(payload, null, 2));
    return payload.totals.detected > 0 && options.failOnDetect ? 1 : 0;
  }

  const manifest = readFixtureManifest();
  console.log(`\nAudit: ${payload.path}`);
  console.log(DISCLAIMER);
  console.log(rule());
  console.log(`Manifest source:  ${payload.manifest_source}`);
  console.log(
    `Files scanned:    ${payload.scan_files.length} ` +
      `(declared shipped surface: ${payload.surface_files.length})`
  );
  console.log("");

  for (const category of payload.categories) {
    const entry = manifest.get(category.category);
    const name = entry && entry.name ? entry.name : "";
    if (category.status === "no-static-detectors") {
      console.log(`${pad(category.category, 8)}${pad(name, 34)}no static detectors`);
      if (category.out_of_artifact.length > 0) {
        console.log(
          `  declared out-of-artifact, not decidable from one package: ` +
            `${category.out_of_artifact.join(", ")}`
        );
      }
      console.log("");
      continue;
    }
    const detected = category.findings.filter((f) => f.detected);
    console.log(
      `${pad(category.category, 8)}${pad(name, 34)}` +
        `${category.findings.length} check(s), ${detected.length} detected  ` +
        `[scope: ${category.scope}]`
    );
    for (const finding of category.findings) {
      const flag = finding.detected ? "DETECTED" : "clear   ";
      console.log(`  ${flag}  ${pad(finding.scenario, 42)}${finding.tier || "untiered"}`);
      console.log(`            ${finding.evidence}`);
    }
    if (category.agent_judgable.length > 0) {
      console.log(
        `  declared, not decided by this run (agent-judgable): ` +
          `${category.agent_judgable.join(", ")}`
      );
    }
    console.log("");
  }

  console.log(rule());
  console.log(
    `Summary: ${payload.totals.checks_run} check(s) over ${payload.totals.categories} categories, ` +
      `${payload.totals.detected} detected; ` +
      `${payload.totals.categories_without_detectors} categories ship no static detector.`
  );
  if (payload.adapter_notes.length > 0) {
    console.log("");
    console.log("Manifest adapter notes (USF v1 -> detector package shape):");
    for (const note of payload.adapter_notes) {
      for (const [index, line] of wrap(note, 72).entries()) {
        console.log(index === 0 ? `  - ${line}` : `    ${line}`);
      }
    }
  }
  if (payload.skipped_files.length > 0) {
    console.log("");
    console.log(`Files not scanned (${payload.skipped_files.length}):`);
    for (const skipped of payload.skipped_files.slice(0, 10)) console.log(`  - ${skipped}`);
    if (payload.skipped_files.length > 10) {
      console.log(`  ... and ${payload.skipped_files.length - 10} more`);
    }
  }
  console.log("");
  console.log(
    "These are detector-level checks, each module's own SCENARIO_TIERS — not coverage"
  );
  console.log(
    "of the whitepaper's named scenarios. See skills/<AST>/coverage-matrix.md and `coverage`."
  );
  return payload.totals.detected > 0 && options.failOnDetect ? 1 : 0;
}

// ---------------------------------------------------------------------------
// Command: coverage
// ---------------------------------------------------------------------------

function buildCoverage() {
  const registry = readRegistry();
  const manifest = readFixtureManifest();
  const rows = [];
  for (const id of AST_IDS) {
    const tiers = registry.byCategory.get(id) || { total: 0 };
    const entry = manifest.get(id);
    const state = f1State(entry);
    rows.push({
      category: id,
      name: entry && entry.name ? entry.name : "",
      scenarios: tiers.total || 0,
      static_detectable: tiers["static-detectable"] || 0,
      agent_judgable: tiers["agent-judgable"] || 0,
      out_of_artifact: tiers["out-of-artifact"] || 0,
      labeled_detectable_checks: entry ? entry.detectable_scenarios : 0,
      fixture_cases: entry ? entry.cases : 0,
      status: entry ? entry.status : "not-in-manifest",
      f1: state.value,
      publishes_f1: state.published,
      no_f1_reason: state.published ? null : state.reason,
    });
  }
  const totals = rows.reduce(
    (acc, row) => ({
      scenarios: acc.scenarios + row.scenarios,
      static_detectable: acc.static_detectable + row.static_detectable,
      agent_judgable: acc.agent_judgable + row.agent_judgable,
      out_of_artifact: acc.out_of_artifact + row.out_of_artifact,
      fixture_cases: acc.fixture_cases + row.fixture_cases,
    }),
    { scenarios: 0, static_detectable: 0, agent_judgable: 0, out_of_artifact: 0, fixture_cases: 0 }
  );
  return { rows, totals };
}

function cmdCoverage(options) {
  const { rows, totals } = buildCoverage();
  const withoutF1 = rows.filter((r) => !r.publishes_f1);
  if (options.json) {
    console.log(
      JSON.stringify(
        {
          source: "scenarios/registry.yaml (tiers) + fixtures/manifest.yaml (corpus, F1 state)",
          categories: rows,
          totals,
          categories_without_f1: withoutF1.map((r) => ({
            category: r.category,
            reason: r.no_f1_reason,
            state: r.f1,
          })),
        },
        null,
        2
      )
    );
    return 0;
  }

  console.log("\nPer-category scenario tiers");
  console.log("source: scenarios/registry.yaml (authoritative on tier) + fixtures/manifest.yaml");
  console.log(DISCLAIMER);
  console.log(rule());
  console.log(
    `${pad("CAT", 8)}${pad("NAME", 32)}${padStart("SCEN", 5)}${padStart("STATIC", 8)}` +
      `${padStart("JUDGE", 7)}${padStart("OUT-ART", 9)}${padStart("CASES", 7)}  F1`
  );
  for (const row of rows) {
    console.log(
      `${pad(row.category, 8)}${pad(row.name, 32)}${padStart(row.scenarios, 5)}` +
        `${padStart(row.static_detectable, 8)}${padStart(row.agent_judgable, 7)}` +
        `${padStart(row.out_of_artifact, 9)}${padStart(row.fixture_cases, 7)}  ${row.f1}`
    );
  }
  console.log(rule());
  console.log(
    `${pad("TOTAL", 40)}${padStart(totals.scenarios, 5)}${padStart(totals.static_detectable, 8)}` +
      `${padStart(totals.agent_judgable, 7)}${padStart(totals.out_of_artifact, 9)}` +
      `${padStart(totals.fixture_cases, 7)}`
  );

  const published = rows.filter((r) => r.publishes_f1);
  console.log("");
  console.log(
    `Categories publishing an F1 number: ${published.length} of ${rows.length}.`
  );
  const emptyTier = withoutF1.filter((r) => r.no_f1_reason === "empty-detectable-tier");
  const pending = withoutF1.filter((r) => r.no_f1_reason === "no-detector-consumes-corpus");
  if (emptyTier.length > 0) {
    console.log("");
    console.log(
      `  declared-and-uncovered — the detectable tier is empty, so no F1 is published ` +
        `and the corpus is never padded to manufacture one (${emptyTier.length}):`
    );
    for (const row of emptyTier) console.log(`    ${pad(row.category, 8)}${row.name}`);
  }
  if (pending.length > 0) {
    console.log("");
    console.log(
      `  pending-detector — a labeled corpus exists and no detector consumes it yet ` +
        `(${pending.length}):`
    );
    for (const row of pending) {
      console.log(
        `    ${pad(row.category, 8)}${pad(row.name, 32)}` +
          `${row.fixture_cases} case(s), ${row.labeled_detectable_checks} labeled check(s)`
      );
    }
  }
  console.log("");
  console.log(
    "A category's F1 denominator is its static-detectable tier only. agent-judgable"
  );
  console.log(
    "scenarios are judged, never folded in; out-of-artifact scenarios never enter a"
  );
  console.log("fixture corpus at all.");
  return 0;
}

// ---------------------------------------------------------------------------
// Command: status
// ---------------------------------------------------------------------------

/**
 * Fixture case directories on disk, and where they disagree with the labels
 * in fixtures/manifest.yaml.
 *
 * The two numbers are reported separately and the difference is named. An
 * unlabeled case directory is invisible to the detector engine and to every
 * F1 denominator, so a single blended "fixtures: N" would hide exactly the
 * drift this repo's tier-lock discipline exists to catch.
 */
function countFixtureCases(manifest) {
  let cases = 0;
  const perCategory = {};
  const unlabeled = [];
  for (const category of listDirs(FIXTURES_DIR)) {
    const dirs = listDirs(join(FIXTURES_DIR, category));
    if (dirs.length === 0) continue;
    perCategory[category] = dirs.length;
    cases += dirs.length;
    const entry = manifest.get(category);
    const labeled = entry ? entry.cases : 0;
    if (labeled !== dirs.length) {
      unlabeled.push({ category, on_disk: dirs.length, labeled, delta: dirs.length - labeled });
    }
  }
  return { cases, perCategory, unlabeled };
}

// Recursive on purpose. Slash commands are namespaced by directory --
// `commands/ast/audit-ast01.md` is the file behind `/ast:audit-ast01` -- so a
// top-level-only scan reports zero commands for a repository that ships
// fourteen. Scorecards are grouped per judge round for the same reason. Dot
// directories and __pycache__ are skipped so a stale cache cannot inflate a
// count this repo publishes as a readiness signal.
function countFiles(dirs, extension) {
  let total = 0;
  const found = [];

  const walk = (dir) => {
    if (!isDir(dir)) return;
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (entry.name.startsWith(".") || entry.name === "__pycache__") continue;
      const full = join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.name.endsWith(extension)) {
        total += 1;
        found.push(full);
      }
    }
  };

  for (const dir of dirs) walk(dir);
  return { total, found };
}

function cmdStatus(options) {
  const skills = discoverSkills();
  const detectors = skills.filter((s) => s.isDetector);
  const manifest = readFixtureManifest();
  const fixtures = countFixtureCases(manifest);
  const manifestCases = [...manifest.values()].reduce((sum, entry) => sum + entry.cases, 0);
  const commands = countFiles(COMMANDS_DIRS, ".md");
  const scorecards = countFiles(SCORECARD_DIRS, ".json");
  const marketplaceSkills = (() => {
    const raw = readText(MARKETPLACE);
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed.skills) ? parsed.skills.length : null;
    } catch {
      return null;
    }
  })();
  const declared = readDeclaredProviders();
  const live = readLiveAdapters().map((adapter) => ({ ...adapter, ...probeAdapter(adapter) }));

  if (options.json) {
    console.log(
      JSON.stringify(
        {
          skills: {
            total: skills.length,
            detectors: detectors.length,
            advisory: skills.length - detectors.length,
            with_detector_module: skills.filter((s) => s.hasDetector).length,
            with_coverage_matrix: skills.filter((s) => s.hasCoverageMatrix).length,
            with_usf_manifest: skills.filter((s) => s.hasUsf).length,
          },
          commands: { total: commands.total, searched: COMMANDS_DIRS.map(relative) },
          marketplace_skills: marketplaceSkills,
          fixtures: {
            case_directories: fixtures.cases,
            manifest_cases: manifestCases,
            per_category: fixtures.perCategory,
            unlabeled: fixtures.unlabeled,
          },
          scorecards: { total: scorecards.total, searched: SCORECARD_DIRS.map(relative) },
          providers: {
            live: live.map((a) => ({
              name: a.name,
              target: a.target,
              configured: a.configured,
              detail: a.detail,
            })),
            declared_unavailable: declared.providers.map((p) => ({
              name: p.name,
              adapter: p.adapter,
              model: p.model,
              status: p.status,
              reason: p.reason,
            })),
            runtime_audit_entries: declared.runtimeEntries,
          },
        },
        null,
        2
      )
    );
    return 0;
  }

  console.log("\nowasp-ast10-agent-skills — status");
  console.log(DISCLAIMER);
  console.log(rule());
  console.log(
    `Skills          ${padStart(skills.length, 4)}  ` +
      `(${detectors.length} AST detectors + ${skills.length - detectors.length} advisory router)`
  );
  console.log(
    `  detector module          ${padStart(skills.filter((s) => s.hasDetector).length, 3)}` +
      `   coverage-matrix.md ${padStart(skills.filter((s) => s.hasCoverageMatrix).length, 3)}` +
      `   skill.usf.yaml ${padStart(skills.filter((s) => s.hasUsf).length, 3)}`
  );
  console.log(
    `Commands        ${padStart(commands.total, 4)}  ` +
      `(searched ${COMMANDS_DIRS.map(relative).join(", ")}` +
      `${marketplaceSkills === null ? "" : `; ${marketplaceSkills} skills declared in .claude-plugin/marketplace.json`})`
  );
  console.log(
    `Fixtures        ${padStart(fixtures.cases, 4)}  ` +
      `case directories under fixtures/ (${manifestCases} labeled in fixtures/manifest.yaml)`
  );
  for (const row of fixtures.unlabeled) {
    console.log(
      `  ${pad(row.category, 26)}${padStart(row.on_disk, 3)} on disk, ` +
        `${padStart(row.labeled, 3)} labeled  ` +
        `-> ${Math.abs(row.delta)} case(s) no F1 denominator can see`
    );
  }
  console.log(
    `Scorecards      ${padStart(scorecards.total, 4)}  ` +
      `(searched ${SCORECARD_DIRS.map(relative).join(", ")})`
  );

  console.log("");
  console.log("Judge providers");
  console.log(rule());
  console.log(
    'live adapters in adapters/ — "configured" is the local precondition each adapter\'s own'
  );
  console.log("check_availability() tests, not a reachability probe:");
  for (const adapter of live) {
    console.log(
      `  ${pad(adapter.name, 30)}${pad(adapter.target, 32)}` +
        `${adapter.configured ? "configured" : "not configured"} — ${adapter.detail}`
    );
  }
  const regions = [...new Set(live.map((a) => a.region).filter(Boolean))];
  if (regions.length > 0) {
    console.log(`  bedrock region: ${regions.join(", ")} (adapters/bedrock.py REGION)`);
  }
  console.log("");
  console.log("declared unavailable in config/audit.yml — recorded with a reason, never");
  console.log("silently dropped or averaged as zero:");
  for (const provider of declared.providers) {
    console.log(`  ${pad(provider.name, 30)}${pad(provider.model || "", 18)}${provider.status}`);
    for (const line of wrap(provider.reason, 66)) console.log(`    ${line}`);
  }
  console.log("");
  console.log(
    `runtime audit entries: ${declared.runtimeEntries} (config/audit.yml runtime_entries, append-only)`
  );
  return 0;
}

function relative(path) {
  return path.startsWith(REPO_ROOT) ? path.slice(REPO_ROOT.length + 1) : path;
}

// ---------------------------------------------------------------------------
// Command: help
// ---------------------------------------------------------------------------

function cmdHelp() {
  console.log(`
OWASP Agentic Skills Top 10 (AST01-AST10) — agent-skill CLI

${DISCLAIMER}

Usage:
  ast10-skills <command> [args]

Commands:
  list [--tier <tier>]     Every shipped skill with its AST id and one-line description.
                           --tier filters by what the skill declares it can decide:
                           ${TIERS.join(" | ")}
  route "<finding>"        Route a free-text finding to its primary AST category using
                           the whitepaper's decision tree, printing the matched rule.
  audit <path>             Run every AST detector over a candidate skill package and
                           print the findings grouped by category.
                           --fail-on-detect exits 1 when any check fires.
  coverage                 Per-category scenario tier counts, and which categories
                           publish no F1 (and for which of the two distinct reasons).
  status                   Skills, commands, fixtures and scorecards present, plus which
                           judge providers are configured and which are declared unavailable.
  help                     This message.

Global:
  --json                   Machine-readable output (every command).

Decision tree used by \`route\` (the whitepaper's own ordering):
  1  the skill itself is malicious at publish time          -> AST01
  2  how the skill reached the registry or pipeline         -> AST02
  3  the SKILL.md / manifest metadata itself                -> AST04
  4  a scanner or reviewer control failed                   -> AST08
  5  more than one matches: record ONE primary root cause, the rest as
     contributing control failures — never split the finding
  AST03/05/06/07/09/10 extend the same tree using each category's own language.

\`route\` and \`audit\` shell out to cli/lib/bridge.py (python3) so the decision tree and
the detectors have exactly one implementation. Override the interpreter with AST10_PYTHON.
`);
  return 0;
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

function parseArgs(argv) {
  const options = { json: false, tier: null, failOnDetect: false };
  const positional = [];
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--json") options.json = true;
    else if (arg === "--fail-on-detect") options.failOnDetect = true;
    else if (arg === "--tier") {
      options.tier = argv[i + 1];
      i += 1;
    } else if (arg.startsWith("--tier=")) options.tier = arg.slice("--tier=".length);
    else positional.push(arg);
  }
  return { options, positional };
}

function main() {
  const [command, ...rest] = process.argv.slice(2);
  const { options, positional } = parseArgs(rest);
  switch (command) {
    case "list":
      return cmdList(options);
    case "route":
      return cmdRoute(positional.join(" "), options);
    case "audit":
      return cmdAudit(positional[0], options);
    case "coverage":
      return cmdCoverage(options);
    case "status":
      return cmdStatus(options);
    case "help":
    case "--help":
    case "-h":
    case undefined:
      return cmdHelp();
    default:
      console.error(`Unknown command: ${command}`);
      cmdHelp();
      return 1;
  }
}

process.exit(main());

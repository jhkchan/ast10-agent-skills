// Test harness: evaluates `sarifText` out of cli/bin/cli.js and reports what it
// does with hostile input. The sanitiser cannot be exercised end to end, because
// no package produces evidence anywhere near the length bound -- the longest
// message the whole fixture corpus emits is about 133 characters -- so a
// package-level test of truncation asserts nothing. This lets a unit test reach
// the function without duplicating it.
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../bin/cli.js", import.meta.url), "utf8");
const start = source.indexOf("function sarifText");
const end = source.indexOf("/** A location ONLY");
if (start < 0 || end < 0) {
  console.error("could not locate sarifText in cli/bin/cli.js");
  process.exitCode = 1;
} else {
  // eslint-disable-next-line no-new-func
  const sarifText = new Function(`${source.slice(start, end)}; return sarifText;`)();
  const CR = String.fromCharCode(13);
  const BELL = String.fromCharCode(7);
  const RLO = String.fromCharCode(0x202e);
  const report = {};
  for (const pad of [998, 999, 1000, 1001]) {
    const out = sarifText("x".repeat(pad) + "\u{1F600}");
    report[`pad${pad}`] = {
      loneSurrogate: [...out].some((c) => {
        const n = c.codePointAt(0);
        return n >= 0xd800 && n <= 0xdfff;
      }),
      codePoints: [...out].length,
    };
  }
  report.stripsCarriageReturn = !sarifText(`a${CR}b`).includes(CR);
  report.stripsBell = !sarifText(`a${BELL}b`).includes(BELL);
  report.stripsBidi = !sarifText(`a${RLO}b`).includes(RLO);
  report.keepsNewline = sarifText("a\nb").includes("\n");
  console.log(JSON.stringify(report));
}

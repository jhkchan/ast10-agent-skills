**DO NOT FILE THIS AS `AST02-S02`.**  

The finding — **mutable version ranges in a nested requirements.txt with no hash pins** — **belongs to AST08**, not AST02. This is a **scanner gap**: the SBOM job detected the presence of underspecified dependencies, but that alone does not indicate compromise — it indicates a missing control that *allows* dependency confusion to go undetected.

Here’s the distinction:
- `AST02-S02 Dependency Confusion` **is not a detectable scenario** from within the package. It is **tiered out-of-artifact** because the actual compromise occurs in the resolver's behavior (e.g., pulling an internal package from a public registry due to naming collision), not in static artifact properties. The package with loose pins is a *victim enabler*, not proof of attack.
- The actual finding here is: **“No hash pins in transitive dependency specification”** — which is **an AST08 failure** (**missed detection due to incomplete scanning of the dependency tree**). The scanner should have enforced or at least flagged the absence of hash-based pins, but it did not.

Therefore:
- **Correct scenario ID**: `AST08-M01` (Misconfigured or Missing Dependency Pinning)
- **Do not use**: `AST02-S02` — per the skill’s design and the `coverage-matrix.md`, this scenario **is not decidable from the artifact** and must not be filed as if it were.

File the ticket under `AST08-M01`, with a description like:  
> "Nested requirements.txt in `pdf-summariser` uses only version ranges (e.g., requests>=2.25.0); no --hash pins present. Risk of undetected dependency confusion due to incomplete SBOM controls."

This accurately reflects the issue and routes it to the correct team: one that owns **scanning policy**, not provenance incident response.
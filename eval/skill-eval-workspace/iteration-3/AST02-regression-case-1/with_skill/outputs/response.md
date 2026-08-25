Do not use AST02-S02 for this finding.

The condition you observed — version ranges without hash pins in a nested requirements.txt — is correctly identified as a supply chain risk, but **you cannot file this under `AST02-S02` (Dependency Confusion)**. According to the decision rules in the `ast02-supply-chain-compromise` skill, this scenario is **out-of-artifact**: Dependency Confusion is a resolver outcome, not something that can be decided from the package alone. The coverage matrix explicitly does not assign `AST02-S02` an in-artifact detection rule, because the actual compromise depends on registry namespace control and resolver behavior, not just the presence of loose pins.

Furthermore, **NEVER file a pin-posture observation under `AST02-S02`**. As stated in the "NEVER" section:  
> "Version ranges rather than `sha256:` pins is that scenario's declared `artifact_signal`, its `artifact_signal_checks` list is empty, and pin posture is a lockfile property while the scenario is a resolver outcome."

This means:
- The lack of hash pins is a real and valid concern — you're right to flag it.
- But it **cannot be truthfully or correctly labeled** as `AST02-S02`.
- Assigning that ID would be an overclaim unsupported by the detection framework.

Instead:
- **Title your ticket with a descriptive label that does not invent a scenario ID**, such as:  
  `Supply Chain Risk: No Hash Pins in Nested requirements.txt (No Valid AST02-S02 Filing)`
- In the body, quote decision rule 4:  
  > "Version ranges are not a security control; hash pins are. `requests>=2.25.0` permits any future release under that range... Hash-checking mode requires *every* package in the transitive tree to carry a hash — a partial pin is not a pin."
- Note that this is a procedural gap enabling Dependency Confusion, but the *finding itself* belongs to broader supply chain policy enforcement, not to an automated `AST02-S02` detection.

There is no valid scenario ID for this artifact-level observation within AST02. File the ticket with accurate language, not a false ID.
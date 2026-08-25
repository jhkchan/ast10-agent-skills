Do not add to the AST01 detection count. The check `AST01-obfuscated-payload-exec` firing with `detected=True` corresponds to scenario **AST08-S02 (Obfuscated Instruction)**, which belongs to category **AST08 (Poor Scanning)**, not AST01.

As stated in the *NEVER* section of the `ast01-malicious-skills` skill:  
**NEVER count a firing `AST01-obfuscated-payload-exec` toward this category.** Its `registry_ids` is `["AST08-S02"]`, and `scenarios/registry.yaml` assigns that scenario to AST08. The `AST01-` prefix here denotes the check's module namespace, not the category of the finding. Reporting this as an AST01 detection would overstate AST01's detection count by one full scenario and misattribute a scanner-capability defect (AST08) to payload behavior (AST01).

Correct classification:  
- **Scenario ID:** AST08-S02  
- **Category:** AST08  
- **Tally impact:** Add to AST08's detection count, not AST01's.  

Update your dashboard accordingly.
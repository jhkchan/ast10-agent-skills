`ast_id: null` — This finding is out of scope for AST01-AST10.

**Reason:** The artifact under review is an MCP server with a tool (`run_sql`) exposed without per-caller authorization. AST01-AST10 categories apply specifically to *skills* — bundles of instructions and resources that an agent loads into its own context. A server-side tool, even one used by agents, is not a skill; it is a server with its own governance, access controls, and operational ownership.

**Where this belongs:** This finding falls under the **MCP Top 10**, which governs server-side extensions and tooling. The condition — missing caller authorization on a powerful server endpoint — is owned by the team operating the MCP server, not by any skill author or client-side agent policy.

**Do not open a ticket in AST01-AST10.** Routing this to AST03 (or any AST category) would misattribute the root cause to a skill that may have simply called a server endpoint as designed. The failure is in server access control, not skill privilege. Escalate to the MCP server’s security team and reference the MCP Top 10 for appropriate handling.
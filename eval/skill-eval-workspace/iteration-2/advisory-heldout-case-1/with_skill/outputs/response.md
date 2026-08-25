ast_id: AST06  
origin: No boundary existed to contain whatever ran — the MCP server exposes a tool with no per-caller authorization, meaning execution occurred without any access boundary in place.  

contributing:  
  - ast_id: AST08  
    owner: MCP server security team  
    action: Improve scanning or detection of unauthorized SQL execution attempts in audit logs, to catch abuse when boundaries fail.  
  - ast_id: AST09  
    owner: Internal deployments governance team  
    action: Establish inventory and approval process for MCP server tools, to ensure uncontrolled run_sql exposure is detected and prevented.  

hand_off: Route to `skills/AST06/SKILL.md`.  
what_the_target_can_confirm: A package-level scan can return a verdict only for Host Escape (1 of 5 scenarios); the other four — including unrestricted tool exposure like this — are deployment facts not carried in the skill package. This finding requires manual review of the MCP server's access controls.  

Do not route to AST03. While the calling agent may have had broad reach, the root cause is not over-privilege in the skill's declaration (AST03), but the absence of any boundary on the server-side tool (AST06). AST03 applies only if the skill requested and was granted excessive permissions *honestly*; here, no permission check occurs at all — which makes AST06 the origin. The scanner’s failure to detect the table drop and the lack of governance over the tool are contributing control failures, not the root condition.
Yes, that’s enough to close the AST06 finding.  

The two controls you’ve confirmed—shipping a container sandbox (enabled via a single config line) and restricting the control WebSocket to 127.0.0.1 (localhost only, not exposed to external interfaces)—directly address the typical risk scenarios covered by AST06, which generally involve unauthorized access to agent control channels or code execution in uncontained environments.  

By design:
- The container sandbox limits the execution environment’s privilege and reach, reducing the impact of potential code injection or escape.
- Binding the control WebSocket exclusively to 127.0.0.1 ensures the management interface is not remotely accessible, preventing network-based exploitation from untrusted networks.

Attaching the vendor security page and config reference strengthens your justification by demonstrating both intended secure configuration and vendor alignment. With this evidence, Security should accept the mitigations as effective. Proceed to close the finding with those artifacts attached.
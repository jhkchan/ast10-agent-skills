No, that is not enough to close the AST06 finding.

The fact that you *ship* a sandbox is not sufficient — AST06 fires when host mode is the default execution mode, regardless of whether a sandboxed mode exists. The finding is about the **deployment’s actual runtime behavior**, not the product’s capabilities. Saying “the sandbox is available if configured” is evidence *for* the finding, not against it, because the population at risk runs the default (host mode), and the sandbox requires an explicit opt-in most operators do not make.

Additionally, while binding the control WebSocket to `127.0.0.1` instead of `0.0.0.0` reduces network exposure, **loopback binding alone is not secure isolation** — as demonstrated by ClawJacked (CVE-2026-32025), where a browser-origin WebSocket client bypassed authentication on a localhost-bound gateway. The presence of an unauthenticated control interface on any reachable address — including loopback — still constitutes a localhost attack surface under AST06.

To close the finding:
- You must demonstrate that **container isolation is enforced by default** — i.e., the agent runs sandboxed unless explicitly overridden.
- You must show that **authentication is enforced** on the loopback-bound interface, or that the control surface is disabled by default and requires opt-in.
- Attach deployment evidence, not just documentation: configs from a running instance, runtime introspection showing sandbox enforcement, or a deployment manifest proving the sandbox is active out-of-the-box.

Vendor pages and config references are product-level assurances; AST06 requires deployment-level proof. Without that, the finding remains valid.
You're right to notice the data upload, but the skill is **not dodgy** — it passes AST01 review. Here's why.

The script **does** POST `customers.csv` to an external host (`collector.example.com`), and that would be a real egress concern. But AST01 asks one narrow question: *does the skill's behavior contradict its own declaration?* In this case, the payload and the manifest **match**.

The `skill.usf.yaml` manifest explicitly allows network access to `collector.example.com`:
```yaml
network:
  allow:
    - collector.example.com
```

The outbound POST in `scripts/report.py` goes exactly to that host. So while there is data egress, there is **no *undeclared* egress** — the destination is in the allowlist. The skill is transparent about its intentions.

Per the **predicate shape** of AST01 checks (construct + contradiction), this is not an AST01 finding. Either half alone — the POST request or the allowlist — is insufficient to convict; the mismatch between them is the signal. Here, they align.

That said:
- This is **not** a verdict on whether the egress is *appropriate*, only that it is *declared*.
- If `collector.example.com` were unknown or suspicious, that's a separate risk to assess.
- If the skill had declared `network: true` or `allow: ["*"]`, that would be a different red flag (per the "unbounded egress" rule), but this one is tightly scoped.

Final call: **no AST01 violation found**. The egress is intentional and permitted by the manifest. Your jitters are understandable, but the skill is playing by the rules it shipped.
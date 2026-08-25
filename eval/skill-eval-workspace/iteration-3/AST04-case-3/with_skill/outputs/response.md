Sign-off: **Approved — no AST04 block**.  

The fixture declares `shell: true` and `network.allow: [api.weather.example]`, which are both required for the `curl` calls in `scripts/fetch.sh`. The destinations accessed (`api.weather.example`) exactly match the allowlist, and there is no permission understating — the declared permissions align with the observed behavior.  

Rule 4 (permission-understating) does not fire because there is no contradiction between the manifest and the code. The `risk_tier` is set to `L2`, which is consistent with granted shell access. No other AST04 scenarios are present: no unsafe deserialization, no spoofed metadata, no invisible smuggling, and no loader misuse.  

All relevant AST04 checks pass per their static-detectable criteria. No scanner gaps (AST08) are indicated.  

✅ Proceed with publication.
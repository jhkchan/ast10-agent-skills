AST04 does not block the approval. The fixture is a labeled clean case for AST04-S4 (permission understating), where the declared network allowlist matches the actual egress destinations in the script. Both `curl` calls in `scripts/fetch.sh` are directed to `api.weather.example`, which is explicitly permitted in the manifest, and `shell: true` is declared. The risk tier is L2, and there is no policy violation.

Sign-off line:  
`Approved for internal marketplace publication — AST04-S4 clean case confirmed, declared permissions match runtime behavior.`
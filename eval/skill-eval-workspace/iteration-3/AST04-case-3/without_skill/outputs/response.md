AST04 does not block the approval. The fixture is correctly labeled as a clean case for AST04-S4 (permission understating), where the declared network allowlist matches all observed egress destinations. Both `curl` calls in `scripts/fetch.sh` target `api.weather.example`, which is explicitly permitted in the manifest under `network.allow`. The use of `shell: true` is consistent with the declared permissions and required for executing the script.

Sign-off line:  
**Approved for publication — observed egress matches declared permissions, no overreach detected.**
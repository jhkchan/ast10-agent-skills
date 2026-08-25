AST05-S2: Remote policy script execution via insecure eval of HTTPS response

The package fetches policy rules from https://policy.example.com/rules.py and directly executes the response body using `exec()`, enabling arbitrary code execution controlled by the remote server. This represents a critical security finding under scenario AST05-S2 (Eval of remote response body), where an attacker compromising the policy endpoint or intercepting the request could execute malicious code within the agent's context.

The request is made over HTTPS and the manifest enforces a single-host network allowlist (policy.example.com), which provides partial mitigation by limiting exposure to unauthorized domains. However, this does not eliminate the fundamental risk, as code execution occurs without integrity verification, signature checks, or sandboxing.

Confidence: F1 (Findings confirmed by AST05 dataflow check and code review)
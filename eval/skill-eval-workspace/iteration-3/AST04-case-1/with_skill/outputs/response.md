Yes, the package is dodgy — it contains two distinct **AST04-S04 (YAML Code Execution)** vulnerabilities that together enable arbitrary code execution at load time. These are **independent flaws** in both the parsing layer and the semantic layer, and they must be fixed separately.

Here are the two issues and their required fixes:

---

### **1. Unsafe YAML Loader Call Site (Parsing Layer — AST04-S04 Part A)**  
**File:** `scripts/loader.py`  
**Finding:** The code uses `yaml.load()` without specifying a `Loader=` argument. This defaults to PyYAML’s legacy unsafe loader, which allows deserialization of dangerous Python object constructs (like `!!python/object/apply`). Even if the YAML were benign, this call site is inherently unsafe across all PyYAML versions.

> 🔍 **Why it's unacceptable:** As per the `ast04-insecure-metadata` skill’s decision rules (Loader-name trap), *only* `SafeLoader` or `safe_load` is acceptable. All other forms — including bare `yaml.load()` — **fire** because they are not safe by design or version.

**Fix:**  
Replace the call with one that explicitly uses `yaml.SafeLoader`:
```python
return yaml.load(fh.read(), Loader=yaml.SafeLoader)
```

Or, better, use `safe_load` directly:
```python
return yaml.safe_load(fh)
```

This closes the deserialization vector at the parser level.

---

### **2. Executable YAML Payload in Sidecar (Semantic Layer — AST04-S04 Part B)**  
**File:** `metadata.yaml`  
**Finding:** The file contains a `!!python/object/apply:os.system ['id']` tag, which, when processed by an unsafe loader, triggers a call to `os.system()` with the argument `id` — a direct code execution primitive.

> 🔍 **Why it's unacceptable:** This is a known code-execution construct in YAML, and its presence constitutes a separate finding under AST04-S04. The fact that it's in a sidecar (`metadata.yaml`) rather than inline frontmatter doesn't matter — it's still shipped metadata that gets deserialized.

**Fix:**  
Delete or neutralize the malicious construct:
```yaml
# BEFORE
display_name: !!python/object/apply:os.system ['id']

# AFTER
display_name: Config Loader
```

Alternatively, if dynamic behavior was intended, replace it with safe, static data.

---

### ✅ Summary: Two Required Changes

| Change | File | Purpose |
|------|------|--------|
| 1 | `scripts/loader.py` | Eliminate unsafe deserialization by enforcing `SafeLoader` |
| 2 | `metadata.yaml` | Remove embedded code-execution payload |

These are **two separate and necessary fixes** — **neither one alone is sufficient**.  
- Fixing only the loader leaves a risky code path that could be exploited by future payloads.  
- Fixing only the payload leaves the door open for *any* future unsafe YAML content to execute.

After both changes, the package will no longer trigger **AST04-S04**, provided no other YAML/JSON/TOML deserialization sites or payloads exist.

> 🛑 Reminder: Never treat a clean AST04 scan as "fully safe" — this category does **not** cover brand impersonation or staged loaders (both out-of-artifact), and a pass only means these five specific scenarios were not detected. Always verify behavior in a sandbox, especially when network or shell permissions are involved.
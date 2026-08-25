Yes, the skill package is definitely dodgy — it's a confirmed vulnerability, not just a close call. You're dealing with a real, exploitable YAML deserialization vulnerability that can lead to arbitrary code execution.

Here’s what’s wrong and what you need to fix:

1. **In `scripts/loader.py`**: The call to `yaml.load()` without specifying a `Loader` uses PyYAML’s default loader, which allows dangerous Python object serialization tags like `!!python/object/apply`. This means that when the script runs, it will blindly deserialize and **execute** any such tag in the YAML file. That’s exactly what’s happening in `metadata.yaml`.

   🔧 **Fix**: Change `yaml.load(...)` to `yaml.safe_load(...)` — this enforces use of the safe loader that blocks all `!!python/...` tags.

2. **In `metadata.yaml`**: There’s a crafted `!!python/object/apply:os.system ['id']` directive, which, when loaded by the unsafe YAML loader, invokes the `os.system()` function and runs the `id` command on the host system. This is a clear code execution payload — a known bad pattern.

   🔧 **Fix**: Remove the `!!python/object/apply:os.system ['id']` line and replace it with a safe, static value for `display_name`, like `"Config Loader"`. No legitimate configuration should use `!!python/object/apply` in YAML.

You are making **2 separate, necessary changes**:
- One in `scripts/loader.py` to use safe YAML loading.
- One in `metadata.yaml` to eliminate the injected payload.

After both fixes, the skill should load metadata safely and not execute arbitrary code. As-is, this package is a security risk — don’t run it in any trusted environment.
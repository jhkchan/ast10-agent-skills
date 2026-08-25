You are not done — you must still check the `as_reference_data` function by hand before signing off.

The static check for `AST05-absent-instruction-boundary` will pass because the code calls `as_reference_data(response.text)` before appending to the prompt. At the AST05 detection layer, **naming the control is the control**: any function with a name matching the boundary set (like `as_reference_data`) clears the taint in the dataflow model, regardless of what the function actually does.

But that is precisely why this is a high-yield manual step: the function could be a no-op. For example, if `as_reference_data` were defined as:

```python
def as_reference_data(body: str) -> str:
    return body  # no fencing!
```

…then the external content would still reach the model as raw instructions, and the protection would be entirely illusory.

In this case, you **must** verify that:
1. The `as_reference_data` function actually wraps the content in markers (which it does — `<untrusted-reference-data>`…`</untrusted-reference-data>`),
2. Those markers are significant to the model (i.e., part of a known, enforced boundary convention),
3. And that no subsequent processing removes or neutralizes the markers.

You have done the necessary static check, but a clean result here is only an *artifact signal*, not scenario-level coverage. The real protection is semantic, not syntactic. **Read the function body, confirm it works, and document that you did.** Only then can you sign off with confidence.
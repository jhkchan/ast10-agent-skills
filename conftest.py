# Repo-root marker for pytest's rootdir/sys.path resolution. Its presence
# here (not just under tests/) is what makes `import adapters.base` work
# from tests/unit/test_adapters.py without a src-layout or an installed
# package — see plan.md T-2.1.

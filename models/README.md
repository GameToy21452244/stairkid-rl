# Canonical model assets

Model binaries are intentionally excluded from Git. Place exact verified files
under `models/cache/` using the filenames in `manifest.json`.

The runtime accepts only the explicit IDs `v3` and `r4`, verifies SHA256 before
and after loading, and never substitutes or falls back to another checkpoint.
Use `python scripts/fetch_models.py --all --source-dir <directory>` to copy and
verify both files. Per-model `--model v3` and `--model r4` modes are also
available. Release URLs are deliberately marked unpublished in the manifest
until actual assets exist; the fetcher never guesses or falls back.

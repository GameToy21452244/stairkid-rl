# Canonical model assets

Model binaries are intentionally excluded from Git. Place exact verified files
under `models/cache/` using the filenames in `manifest.json`.

The runtime accepts only the explicit IDs `v3` and `r4`, verifies SHA256 before
and after loading, and never substitutes or falls back to another checkpoint.
Use `python scripts/fetch_models.py --all` to download and verify both files
from the `real-data-preservation-v1` GitHub Release. Per-model `--model v3` and
`--model r4` modes are also available, while `--source-dir <directory>` supports
offline installation. The fetcher never guesses or falls back.

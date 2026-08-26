# Canonical model assets

Model binaries are intentionally excluded from Git. Place exact verified files
under `models/cache/` using the filenames in `manifest.json`.

The runtime accepts only the explicit IDs `v3` and `r4`, verifies SHA256 before
and after loading, and never substitutes or falls back to another checkpoint.
The automated release-asset fetch workflow is deferred to M3.

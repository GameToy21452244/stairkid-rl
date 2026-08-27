# External training assets

`manifest.json` is the canonical SHA-pinned inventory. Large assets belong in
the ignored `training_assets/cache/` directory and are never repository source.

The R4 frozen-R1 ZIP is retained only as a historical transport bundle for
checkpoints and targeted banks. The fetch/staging code verifies its bundle SHA
and the embedded checkpoint and bank-manifest SHA values. Its Release URL is
currently unpublished, so supply the exact file through `--source-dir`.

See `docs/TRAINING.md` for commands and safety constraints.

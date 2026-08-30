# External training assets

`manifest.json` contains one external SHA-pinned asset: the R4 frozen-R1
bundle. Large assets belong in the ignored `training_assets/cache/` directory
and are never repository source.

The R4 frozen-R1 ZIP is retained only as a historical transport bundle for
checkpoints and targeted banks. The fetcher verifies the bundle SHA. Staging
then checks the embedded seed/checkpoint pairing, metadata, ZIP integrity,
bank schema/content, snapshot integrity, and dynamic checkpoint-to-bank
identity without exposing separate child SHA prerequisites. The canonical URL
points to the `real-data-preservation-v1` GitHub Release; `--source-dir`
supports offline installation.

See `docs/TRAINING.md` for commands and safety constraints.

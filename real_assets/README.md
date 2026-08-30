# Canonical Real detector assets

`canonical_v1` is the ready-to-use detector calibration for the project's
canonical NS-SHAFT build and 634x431 captured client. `FIRST_RUN_SETUP.cmd`
copies these small, SHA-verified templates into the ignored local
`captures/templates/` directory without overwriting user calibration.

The templates were reconstructed from the preserved `real-data-preservation-v1`
Release evidence. The manifest records source provenance and the frozen
46-video offline holdout result. No Real control or keyboard input was used to
build or validate them.

`CALIBRATE_REAL_GAME.cmd` remains a fallback for a different game build,
capture geometry, visual theme, or a detector compatibility failure.

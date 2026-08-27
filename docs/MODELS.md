# Canonical models

`models/manifest.json` is the only active registry and contains exactly `v3`
and `r4`. No model is a default, champion, or fallback. Assets remain outside
Git under the ignored `models/cache/` directory.

## Fresh V3

- ID: `v3`
- Seed / timesteps: `17 / 524288`
- SHA-256: `e539ad8e9a39991d738ef9d4113968d933d4f2535e3b08fabe27f3b4ffd9f51e`
- Status: `STABLE_BASELINE`
- Historical Real evidence: N=61, mean=4.41, median=4, Q25=2, Q75=6,
  floor<=4=59.0%.

## V3.5 R4

- ID: `r4`
- Seed / timesteps: `142 / 655360`
- SHA-256: `6a9e966ae69c1b3f5610bc5c8a009dcc5519e94fa20d754e54ef0ac445399e10`
- Status: `EXPERIMENTAL_FINAL`
- Formal simulator gate: FAIL
- Formal promotion: NO
- Safety: UNRESOLVED
- Exploratory Real20: N=20, mean=5.35, median=5, Q25=3, Q75=8,
  min=1, max=13, floor<=4=45%.

R4 showed a descriptively stronger Real-game floor distribution than the
historical Fresh V3 sample. Statistical superiority was not established and
safety remained unresolved.

The loader verifies the canonical archive hash before and after load, then
checks timesteps, observation shape, and action space. The historical R4
policy-parameter digest is provenance only (recorded in `PROJECT_HISTORY.md`),
not a second runtime gate.

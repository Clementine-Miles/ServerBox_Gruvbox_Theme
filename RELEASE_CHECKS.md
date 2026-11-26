# Release candidate checks

This revision incorporates findings H1–H6, M2, M4 and L1–L3 of the independent `SERVERBOX-GRUVBOX-AUDIT.md` where they can be addressed by a theme. C1 remains a publication prerequisite, while M1/M3/M5 and hardcoded app colors need upstream fixes or explicit acceptance of limitations.

## Executed on revised source

- Deterministic manifest regeneration: PASS; byte-identical on a second generation.
- Independent local validation (`python tools/audit.py`): 16 resolved appearances, 3,040 targeted theme-side measurement rows PASS, zero FAIL. 160 separately classified upstream rows: 44 PASS, 116 FAIL (hardcoded statistics and legacy seed). 48 conditional fill-only rows FAIL; actual selected cues require UI verification. These are modeled rows, not a full WCAG test or a count of independent bugs. The new model differs from the earlier independent audit, so total counts are not directly comparable.
- Canonical surface/variant checks and explicit 46 roles: PASS under local resolver.
- Official `pack.py`, Git blob `506aae37fb31a72eea2e7f274ae184c54987f352`: PASS; both packages repeated byte-identically and root manifest bytes checked.
- Missing official checker regression: PASS; release wrapper refused to continue (exit 2).
- Full pinned JSON Schema, official validator, publisher dry-run and native Rust parser of revised bytes: NOT TESTED. The execution environment cannot resolve raw.githubusercontent.com and does not have check-jsonschema. Previous audit results apply to the old revision only.
- Android, current Linux, Monitor runtime tests of revised bytes: NOT TESTED. Public upload, store ingestion and catalog PR: NOT PERFORMED.

## Main corrections and trade-offs

Removed global primary and Orange button fill/state overrides; preserve native tone-specific button semantics. Keep independent focus borders for outlined/text/icon controls without conflicting pressed/hover border overrides. Increase contrast for actual primary and error text on neutral or accent-tinted substrates. Give `outline` text contrast on Monitor settings cards. Retain canonical selected accent in non-text progress and slider fields. The adjusted primary Dark tones are intentionally lighter, and Light tones darker, than the Vim anchors. Recomputed the foregrounds for tonal button ink and chip states. Preserve distinct raised dark surface rungs. Optimize one mid-tone seed over modeled cross-mode substrates rather than paint Dark primary directly in Light. Preserve existing IDs, palette family, variant order and surface anchors. The local regression oracle uses independent source-over sRGB calculations and separates upstream and conditional evidence from theme-side gates. Missing schema now blocks release checks; exact listing structure and version types are validated.

## Required manual gates

Run the release wrapper with the actual GitHub origin and pinned official schema available. Read every warning. Test both packages on Android and/or desktop, all eight variants in Light and Dark, and verify the actual controls and palette identity. Exercise services Stop, selected/focused storage, dialogs, input, native button states, connection badges and statistics, and Monitor if distributing for that UI. Verify rendered selection cues. Review any upstream limitations with the maintainer; do not claim app-wide accessibility. After publishing, compare each public asset against the exact validated preview, verify version records and verify the public default-branch archive and test both direct HTTPS package URLs before opening the catalog PR.

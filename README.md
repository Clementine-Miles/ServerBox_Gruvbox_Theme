# ServerBox Gruvbox themes

Two independent, MIT-licensed themes adapted from [Gruvbox](https://github.com/morhetz/gruvbox) and [Gruvbox Material](https://github.com/sainnhe/gruvbox-material). Green and Blue choose the primary accent without removing the other Gruvbox hues. No ServerBox source changes, icons, fonts, wallpapers or runtime dependencies are required.

**Status:** revised release candidate. The independent local regression model passed its selected theme-side checks, and the exact pinned official packer produced reproducible previews. Full official schema/validator, publisher dry-run and real-app tests must be repeated on these revised bytes before publication. The previous independent audit tested the earlier manifests, not these bytes. See `RELEASE_CHECKS.md`.

## Variants

| Package | Native key | Label | Dark | Light |
|---|---|---|---|---|
| `milesclem.gruvbox` | `green` | Green | `#282828` | `#FBF1C7` |
| | `blue` | Blue | `#282828` | `#FBF1C7` |
| `milesclem.gruvbox-material` | `medium_green` | Medium Green | `#282828` | `#FBF1C7` |
| | `medium_blue` | Medium Blue | `#282828` | `#FBF1C7` |
| | `hard_green` | Hard Green | `#1D2021` | `#F9F5D7` |
| | `hard_blue` | Hard Blue | `#1D2021` | `#F9F5D7` |
| | `soft_green` | Soft Green | `#32302F` | `#F2E5BC` |
| | `soft_blue` | Soft Blue | `#32302F` | `#F2E5BC` |

The first variant of each family is the default. All variants support System, Light and Dark. Schema compatibility is 3–4. Material uses the canonical `material` foreground branch, with adapted tones for text, containers and controls. Its Hard/Medium/Soft ladder and all core surfaces are independent of accent selection.

## Color design

The generator preserves the canonical red, orange, yellow, green, aqua, blue and purple anchors. The `primary` and `error` roles are contrast-adjusted because ServerBox also paints them directly as text, including tinted count backgrounds. The canonical selected Green or Blue is retained on the progress and slider controls, Orange on secondary roles and selected chip/card backgrounds, Purple on connection badges, Aqua on supporting text actions, Yellow on tooltips and the complementary accent on search and native icon buttons. Standard Flutter filled, tonal and elevated buttons retain their native semantic color pairs and state ink. Outlined buttons no longer force Orange backgrounds. All 46 ColorScheme roles are explicit, and surface tint is transparent.

## Local installation

Desktop: Settings > Appearance > Install theme > Folder, then select one of the two package folders under `themes/`. On mobile, choose File and select a packed `.fsbt`. Choose the variant, then the desired appearance mode. The app can reset manual Light/Dark to System when applying a different variant or reimporting a package; select the appearance again if needed.

## Development and release

Prerequisites: Python 3.11+, Git and authenticated GitHub CLI for publishing. Only development validation needs `check-jsonschema` and `jsonschema`. For example:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install check-jsonschema==0.38.2
python tools/generate.py
python tools/audit.py
```

The release wrapper checks the exact pinned official tool and schema Git blob hashes, requires the full checker, verifies regeneration, runs both official validators, packages twice, checks package bytes and runs the official publisher dry-run. It never publishes. Use an empty external output directory and a real GitHub origin:

```sh
python tools/release_check.py --preview-dir ../gruvbox-previews
```

Alternatively pass `--serverbox /absolute/path/to/pinned/serverbox` to use a local checkout. `--skip-dry-run` is for local previews before origin exists; it does not skip schema validation. Inspect the output and test the new files on an actual app before publishing. The pinned ServerBox revision is `fa7941a0b3d4dda154cbf85b007dc6348812e679`; its `fl_lib` gitlink is `4e321dfb7b9e7abd0c1658f1ea196e03e2cdaad5`.

To publish, obtain that checkout, set `UPSTREAM` to its absolute path and use the official tool from the checkout. `repo.toml` and both listings already exist; do not run `--init` again. The official publisher creates immutable versioned assets in the `themes` prerelease and appends listing version records. Review current upstream instructions before publishing:

```sh
ROOT=$(pwd -P)
SCRIPT="$UPSTREAM/.claude/skills/serverbox-theme/scripts/publish.py"
(cd "$UPSTREAM" && python "$SCRIPT" --root "$ROOT" --dry-run)
# Only after successful validation and manual app acceptance:
(cd "$UPSTREAM" && python "$SCRIPT" --root "$ROOT")
python tools/audit.py --require-versions
# Verify publicly served package bytes against validated previews before pushing listings.
```

Commit and push the version records. The theme store reads the default branch; register this public GitHub repository in ServerBox's `assets/catalog/repos.toml` with one `[[repo]]` entry per repository. Do not commit generated release assets to the source repository. The publisher never intentionally replaces an existing version's bytes; if a released theme changes, publish a new version. A proposed owner/repository is already set in the two listing homepages; verify that it matches your actual GitHub origin.

## Known limitations

The current upstream application uses a single seed for both modes, some native charts and direct legacy focus/progress paint. The chosen mid-tone seed improves the weakest cases but cannot satisfy all contrasts on both modes simultaneously. Connection statistics use hardcoded red/green/gray text, independent of theme fields. Some selected fills have low standalone contrast; evaluate associated glyphs, text, shape and focus cues in the application. Monitor Desk also derives its own HCT tonal scales. No theme-only change can guarantee application-wide WCAG conformance or preserve manual mode on the existing variant-apply path. These are documented upstream limitations, not reasons to add unsupported fields.

## References and license

- [Theme Authoring](https://serverbox.lollipopkit.com/docs/development/theme-authoring/)
- [Official authoring skill and tools](https://github.com/lollipopkit/flutter_server_box/tree/main/.claude/skills/serverbox-theme)
- [Maintainer approval, Issue #1976](https://github.com/lollipopkit/flutter_server_box/issues/1976#issuecomment-7153834959)
- [Gruvbox Original pinned palette](https://github.com/morhetz/gruvbox/tree/ef8864bb42bf244f0295d1c5a403b27e3d139695)
- [Gruvbox Material pinned palette](https://github.com/sainnhe/gruvbox-material/tree/11d779b26a9ab2b3db8c22c6ac9fb6e8ed4fea79)

MIT; see `LICENSE` and `THIRD_PARTY_NOTICES.md`. Both standalone manifests retain attribution and permission terms.

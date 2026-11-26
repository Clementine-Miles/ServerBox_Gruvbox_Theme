# ServerBox Gruvbox themes

Two MIT-licensed themes for ServerBox, adapted from Gruvbox and Gruvbox Material. Both support System, Light, and Dark on theme schemas 3–4.

| Theme | Variants |
| --- | --- |
| [Gruvbox](themes/milesclem.gruvbox/) | Green, Blue |
| [Gruvbox Material](themes/milesclem.gruvbox-material/) | Medium, Hard, and Soft, each with a Green or Blue accent |

## Install

In ServerBox, open **Settings → Appearance → Install theme**.

- **Desktop.** Choose **Folder** and select one of the theme folders above.
- **Mobile.** Choose **File** and select a packed `.fsbt`.

Select a variant, then set your appearance mode. Changing variants or reimporting may reset Light or Dark to System.

## Develop and validate

With Python 3.11+ and a GitHub `origin`, run from the repository root. Use an empty output directory outside the checkout.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install check-jsonschema==0.38.2
python tools/release_check.py --preview-dir ../gruvbox-previews
```

The release check verifies manifest regeneration, validates both themes with the pinned ServerBox tools, packs each theme twice to verify reproducibility, and runs the publisher in dry-run mode. To regenerate after editing the palettes, run `python tools/generate.py`.

## Release

Test both packages in ServerBox before publishing. Use the official publisher with an authenticated GitHub CLI and the existing theme listings, then verify the uploaded bytes and commit the version records. Follow the [release checklist](RELEASE_CHECKS.md) and [ServerBox publishing guide](https://github.com/lollipopkit/flutter_server_box/blob/fa7941a0b3d4dda154cbf85b007dc6348812e679/.claude/skills/serverbox-theme/SKILL.md#publishing-in-your-own-repository).

See the [MIT license](LICENSE) and [upstream palette credits](THIRD_PARTY_NOTICES.md).

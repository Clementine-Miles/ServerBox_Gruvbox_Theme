# Runtime and release checks

Run `python tools/release_check.py --preview-dir ../gruvbox-previews --verify-public-assets`. The GitHub validation workflow can run the same checks and upload the previews as a build artifact.

Before publishing, import both previews on the platforms targeted for release. Include Android for the SSH rendering check. Open all eight variants in Light and Dark, and verify System by changing the OS appearance. Check card and dialog elevation, bottom navigation and the rail, forms, menus, selection cues, and the Monitor and storage views. Exercise rest, hover, focus, press, and disabled states. Check in particular the Services Stop action, selected file rows, connection badges, and warning and error text.

On a ServerBox build with the [SSH patch](docs/serverbox-terminal-appearance.patch), check the SSH page and floating view with Light and Dark app appearance crossed with Follow App, Light, and Dark terminal settings. Exercise terminal text, ANSI foregrounds and backgrounds, cursor, selection, and idle and armed keys. Repeat with an SSH background image, with a missing image, and after changing terminal appearance while a session is open. The [terminal palette notes](docs/colors.md) describe which parts the renderer supports.

After runtime acceptance, use the official publisher with a new version for new bytes. Compare each public download to the validated preview and verify the listing records and default-branch catalog archive. [ServerBox publishing guide](https://github.com/lollipopkit/flutter_server_box/blob/fa7941a0b3d4dda154cbf85b007dc6348812e679/.claude/skills/serverbox-theme/SKILL.md#publishing-in-your-own-repository)

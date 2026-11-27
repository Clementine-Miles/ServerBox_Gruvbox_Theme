# Palette and ServerBox compatibility

The generator uses four layers. Canonical anchors come from the Vim palettes, with the original Hard, Medium, and Soft `bg0` values shared by both families. The semantic palette assigns red to failure, orange to warning, yellow to attention, green to success, aqua to network activity, blue to information, and purple to specialized actions. The component palette selects surfaces and adjusts only the tones a particular foreground, fill, or state needs. The terminal palette is compiled separately for xterm. [Gruvbox source](https://github.com/morhetz/gruvbox/blob/ef8864bb42bf244f0295d1c5a403b27e3d139695/colors/gruvbox.vim#L89) · [Gruvbox Material source](https://github.com/sainnhe/gruvbox-material/blob/11d779b26a9ab2b3db8c22c6ac9fb6e8ed4fea79/autoload/gruvbox_material.vim#L44)

The pinned ServerBox revision is `fa7941a` and the current main revision reviewed was `e0347a0`. They have the same FSBT schema, SSH code, xterm revision, and shared theme parser and styling code. Their brush and widget behavior was checked against Flutter 3.50.1. Both theme IDs, the variant order, and the schema 3–4 range are preserved. [Pinned ServerBox](https://github.com/lollipopkit/flutter_server_box/tree/fa7941a0b3d4dda154cbf85b007dc6348812e679) · [Current ServerBox](https://github.com/lollipopkit/flutter_server_box/tree/e0347a02f5ca60edf1d635a158c6ba162aef7e76) · [FSBT schema](https://github.com/lollipopkit/flutter_server_box/blob/e0347a02f5ca60edf1d635a158c6ba162aef7e76/docs/schemas/fsbt-manifest.schema.json)

## Application components

| Surface or control | Resolved colors and interaction |
| --- | --- |
| AppBar, cards, tiles, and sidebar | Canonical page surface with elevated warm cards. Muted icons and secondary labels have their own ink. The sidebar selection has its own fill because Monitor layers translucent counts over it. |
| Bottom navigation, rail, and tabs | Selected navigation icons use the accent container pair, with labels on the surrounding panel. Shared segmented tabs use `primaryContainer`. Material tabs and segments retain their own active glyphs, overlays, and disabled behavior. |
| Filled, elevated, tonal, outlined, text, and icon buttons | Flutter supplies the foreground, background, and state layers. Text, outlined, and icon buttons have visible focus rings. Error labels such as Services Stop can retain their widget-local pair. |
| Input and search | Stable text and hint colors with separate focus, error, and disabled outlines. The blue search icon and red error border use tones suited to their backgrounds. Native text selection still uses the primary role at 40% opacity on Material platforms. |
| Dialogs, sheets, menus, tooltips, and toasts | Raising surfaces separates overlays from the page. Tooltips use yellow with paired warm ink, toasts use inverse roles, and sheet grips use the readable outline. |
| Chips, badges, switches, sliders, progress, dividers, and scrollbars | Chips and switches retain native state resolution. Badges use a purple pair. Generic progress and slider tracks use the chosen accent and an accent-tinted track. Scrollbar ink is readable on the track and adjacent surface. Divider lines are decorative. |

ServerBox derives chart series from the theme seed and owns fixed status colors. The resource anchors in the palette specification record yellow for CPU, purple for memory, orange for disk and aqua for network. FSBT has no component field for the native text selection overlay or the borders of legacy widgets that paint the seed directly. The audit also measures the fill alone where selection may have an icon, indicator, checkmark, or heavier label. [Palette specification](terminal-palettes.json) · [Shared theme application](https://github.com/lollipopkit/fl_lib/blob/41f01b6c8dacf7204bc8717499780bc3a8aa42b5/lib/src/theme/components.dart) · [ServerBox monitoring colors](https://github.com/lollipopkit/flutter_server_box/blob/e0347a02f5ca60edf1d635a158c6ba162aef7e76/lib/data/res/chart_palette.dart)

## SSH terminal

Stock ServerBox resolves a full xterm theme through `TerminalLook`. The SSH page sets terminal opacity to zero and exposes the app scaffold. Its Light terminal can therefore draw black text and key labels onto the dark app surface, and the reverse mismatch occurs with Dark terminal in a Light app. The floating terminal already paints its own backdrop, but still uses black or white key labels and the app seed for armed keys. FSBT schemas 3–4 have no terminal table. [TerminalLook](https://github.com/lollipopkit/flutter_server_box/blob/e0347a02f5ca60edf1d635a158c6ba162aef7e76/lib/data/res/terminal.dart) · [SSH page](https://github.com/lollipopkit/flutter_server_box/blob/e0347a02f5ca60edf1d635a158c6ba162aef7e76/lib/view/page/ssh/page/page.dart) · [Floating terminal](https://github.com/lollipopkit/flutter_server_box/blob/e0347a02f5ca60edf1d635a158c6ba162aef7e76/lib/view/page/ssh/float.dart)

Apply the [ServerBox patch](serverbox-terminal-appearance.patch) in a ServerBox checkout. It is checked against both revisions above. With Flutter 3.50.1 and the checkout's submodules available, run the SSH widget regression and rebuild ServerBox.

```sh
git apply --check /path/to/serverbox-terminal-appearance.patch
git apply /path/to/serverbox-terminal-appearance.patch
flutter test test/widget/ssh_tab_test.dart
```

The two SSH hosts use one resolved `TerminalAppearance` for the canvas, xterm theme, virtual keys, and system keyboard brightness. Explicit terminal modes win over app brightness. The SSH image retains its configured opacity over the terminal backdrop, and the virtual key strip uses a solid terminal surface. Contrast over a user-selected image depends on that image and its opacity.

The patch uses ServerBox's built-in terminal themes, with brightness-specific ANSI colors where the existing stock tones were unreadable. To integrate the separate Gruvbox profiles in a ServerBox build, read the chosen family and level from [terminal-palettes.json](terminal-palettes.json) and pass its Light and Dark `TerminalTheme` values to `TerminalAppearance.resolve`. Each ARGB field names the corresponding xterm constructor argument. This integration requires a ServerBox code change. Current xterm uses the selection overlay. The palette also defines the search fields and `selectionCursor`, which this patch uses as the armed-key accent. The checked-in xterm renderer has no consumer for the search fields. [xterm theme fields](https://github.com/lollipopkit/xterm.dart/blob/dbb85324999bb6e339e364de1f8d2b03af0318e7/lib/src/ui/terminal_theme.dart)

The 12 profiles cover both modes at all three contrast levels. Ordinary text, all 12 chromatic ANSI slots, and bright black meet 4.5:1 over their own canvas, including through xterm's selection overlay. Every indexed ANSI fill has a 4.5:1 pair with ANSI black or bright white. Explicit dark-on-dark and light-on-light neutrals and arbitrary program-supplied color pairs still depend on the program. The audit checks contrast and inheritance without running the widgets. The [runtime and release checks](../RELEASE_CHECKS.md) cover the interaction and platform acceptance steps.

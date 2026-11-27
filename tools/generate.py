#!/usr/bin/env python3
"""Generate the FSBT manifests and the separate xterm palette specification."""
from __future__ import annotations

import argparse
from colorsys import hls_to_rgb, rgb_to_hls
from dataclasses import dataclass
from functools import cache
import json
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SERVERBOX = "fa7941a0b3d4dda154cbf85b007dc6348812e679"
SCHEMA_URL = (
    f"https://raw.githubusercontent.com/lollipopkit/flutter_server_box/{SERVERBOX}"
    "/docs/schemas/fsbt-manifest.schema.json"
)
FAMILIES = {"original": "Gruvbox", "material": "Gruvbox Material"}
MODES = ("dark", "light")
LEVELS = ("medium", "hard", "soft")
ACCENTS = ("green", "blue")
TEXT = 4.55  # Leave room for rounding state layers to eight bits.
GRAPHIC = 3.05
BUTTON_INK = 26 / 255


# Canonical palette (colors/gruvbox.vim and autoload/gruvbox_material.vim).
BG0 = {
    "dark": {"hard": "1D2021", "medium": "282828", "soft": "32302F"},
    "light": {"hard": "F9F5D7", "medium": "FBF1C7", "soft": "F2E5BC"},
}
DARK_NEUTRALS = ("3C3836", "504945", "665C54", "7C6F64")
LIGHT_NEUTRALS = ("EBDBB2", "D5C4A1", "BDAE93", "A89984")
GRAY = "928374"
HUES = ("red", "orange", "yellow", "green", "aqua", "blue", "purple")
ACCENT_ANCHORS = {
    "original": {
        "dark": "FB4934 FE8019 FABD2F B8BB26 8EC07C 83A598 D3869B",
        "light": "9D0006 AF3A03 B57614 79740E 427B58 076678 8F3F71",
    },
    "material": {
        "dark": "EA6962 E78A4E D8A657 A9B665 89B482 7DAEA3 D3869B",
        "light": "C14A4A C35E0A B47109 6C782E 4C7A5D 45707A 945E80",
    },
}
ORIGINAL_NEUTRAL = dict(zip(HUES, "CC241D D65D0E D79921 98971A 689D6A 458588 B16286".split()))
# The Material foreground pairs fg0 and fg1.
MATERIAL_INK = {"dark": ("D4BE98", "DDC7A1"), "light": ("654735", "4F3829")}
# Material bg_dim, bg1, bg_statusline2, bg3, bg5 (dark) or bg1–bg5 (light).
MATERIAL_SURFACES = {
    "dark": {
        "hard": ("141617", BG0["dark"]["medium"], BG0["dark"]["soft"], *DARK_NEUTRALS[:2]),
        "medium": ("1B1B1B", BG0["dark"]["soft"], "3A3735", "45403D", "5A524C"),
        "soft": ("252423", DARK_NEUTRALS[0], "46413E", *DARK_NEUTRALS[1:3]),
    },
    "light": {
        "hard": ("F5EDCA", "F3EAC7", BG0["light"]["soft"], "EEE0B7", LIGHT_NEUTRALS[0]),
        "medium": ("F4E8BE", BG0["light"]["soft"], "EEE0B7", "E5D5AD", "DDCCAB"),
        "soft": ("EDDEB5", LIGHT_NEUTRALS[0], "E6D5AE", "DAC9A5", LIGHT_NEUTRALS[1]),
    },
}
# Material's visual feedback fills, in red/green/blue/purple order.
MATERIAL_VISUAL = {
    ("dark", "hard"): "442E2D 333E34 2E3B3B 3C333B",
    ("dark", "medium"): "4C3432 3B4439 374141 443840",
    ("dark", "soft"): "543937 424A3E 404946 4B3E45",
    ("light", "hard"): "F0DDC3 DDE5C2 D9E1CC EEE2D1",
    ("light", "medium"): "F1D9B5 DEE2B6 DADEC0 EFDEC3",
    ("light", "soft"): "EFD2B3 D7D9AE D3D5B8 E8D4BA",
}
DEEP_INK = MATERIAL_SURFACES["dark"]["hard"][0]
PALE_INK = BG0["light"]["hard"]


def anchors(family, mode):
    return dict(zip(HUES, ACCENT_ANCHORS[family][mode].split()))


def rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def hex_rgb(channels):
    return "".join(f"{round(channel):02X}" for channel in channels)


def blend(background, ink, opacity):
    return hex_rgb(bg + (fg - bg) * opacity for bg, fg in zip(rgb(background), rgb(ink)))


@cache
def luminance(color):
    def linear(channel):
        value = channel / 255
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    return sum(weight * linear(value) for weight, value in zip((.2126, .7152, .0722), rgb(color)))


def contrast(first, second):
    low, high = sorted((luminance(first), luminance(second)))
    return (high + .05) / (low + .05)


def lighter(color, amount):
    hue, lightness, saturation = rgb_to_hls(*(value / 255 for value in rgb(color)))
    return hex_rgb(value * 255 for value in hls_to_rgb(
        hue, min(1, max(0, lightness + amount)), saturation
    ))


def fit_tone(anchor, mode, usable):
    """Move only HSL lightness, starting at the canonical anchor."""
    direction = 1 if mode == "dark" else -1
    for step in range(501):
        candidate = lighter(anchor, direction * step / 500)
        if usable(candidate):
            return candidate
    raise ValueError(f"No {mode} contrast tone for #{anchor}")


def readable(anchor, mode, backgrounds, *, minimum=TEXT, ink=0):
    return fit_tone(anchor, mode, lambda color: all(
        contrast(color, blend(bg, color, ink) if ink else bg) >= minimum
        for bg in backgrounds
    ))


def fill_pair(anchor, mode, *, ink=0):
    """Return a colored fill and its warm foreground at rest and under ink."""
    warm = (DEEP_INK, PALE_INK) if mode == "dark" else (PALE_INK, DEEP_INK)
    for foreground in warm:
        if contrast(foreground, blend(anchor, foreground, ink)) >= TEXT:
            return anchor, foreground
    foreground = max(warm, key=lambda color: contrast(color, anchor))
    fill_mode = "dark" if foreground == DEEP_INK else "light"
    fill = fit_tone(anchor, fill_mode, lambda color:
                    contrast(foreground, blend(color, foreground, ink)) >= TEXT)
    return fill, foreground


def surfaces(family, level, mode):
    page = BG0[mode][level]
    if family == "material":
        rungs = MATERIAL_SURFACES[mode][level]
        if mode == "light":
            rungs = (page, *rungs[:4])
        foreground, quiet = MATERIAL_INK[mode]
    elif mode == "dark":
        low = blend(page, DARK_NEUTRALS[0], .5)
        rungs = (BG0[mode]["hard"], low, DARK_NEUTRALS[0],
                 blend(*DARK_NEUTRALS[:2], .5), DARK_NEUTRALS[1])
        foreground, quiet = LIGHT_NEUTRALS[:2]
    else:
        low = BG0[mode]["soft"]
        rungs = (BG0[mode]["hard"], low, LIGHT_NEUTRALS[0],
                 blend(*LIGHT_NEUTRALS[:2], .5), LIGHT_NEUTRALS[1])
        foreground, quiet = DARK_NEUTRALS[:2]

    lowest, low, container, high, highest = rungs
    if family == "material" and level == "soft" and mode == "dark":
        # Leave room for Material's 40% text selection tint on dialog fields
        # while keeping body text warm and the canonical page surface intact.
        container = blend(low, container, .5)
    dim, bright = (lowest, highest) if mode == "dark" else (highest, lowest)
    return {
        "surface": page, "surfaceDim": dim, "surfaceBright": bright,
        "surfaceContainerLowest": lowest, "surfaceContainerLow": low,
        "surfaceContainer": container, "surfaceContainerHigh": high,
        "surfaceContainerHighest": highest,
    }, foreground, quiet


# Semantic palette. The progress theme controls generic readings. ServerBox's
# ChartPalette and StatePalette own per-series and status colors.
SEMANTIC_HUES = {
    "failure": "red",
    "warning": "orange",
    "attention": "yellow",
    "success": "green",
    "network": "aqua",
    "information": "blue",
    "specialized": "purple",
}
RESOURCE_HUES = {
    "cpu": "attention", "memory": "specialized", "disk": "warning", "network": "network",
}


@dataclass(frozen=True)
class SemanticPalette:
    accent: str
    colors: dict[str, str]
    resources: dict[str, str]
    fills: dict[str, str]


def semantic_palette(family, level, mode, accent):
    palette = anchors(family, mode)
    colors = {name: palette[hue] for name, hue in SEMANTIC_HUES.items()}
    resources = {name: colors[use] for name, use in RESOURCE_HUES.items()}
    page = BG0[mode][level]
    fills = {hue: blend(page, value, .17 if mode == "dark" else .12)
             for hue, value in palette.items()}
    if family == "material":
        fills.update(zip(("red", "green", "blue", "purple"),
                         MATERIAL_VISUAL[mode, level].split()))
    return SemanticPalette(palette[accent], colors, resources, fills)


# Component palette. Keep Flutter's stateful defaults for pairs the component
# schema would replace with a single value (e.g. switches and chip labels).
def component_palette(family, level, mode, accent):
    semantic = semantic_palette(family, level, mode, accent)
    surface_roles, foreground, quiet = surfaces(family, level, mode)
    page = surface_roles["surface"]
    low = surface_roles["surfaceContainerLow"]
    raised = surface_roles["surfaceContainer"]
    high = surface_roles["surfaceContainerHigh"]
    highest = surface_roles["surfaceContainerHighest"]
    warning = semantic.fills["orange"]
    selections = {name: semantic.fills[name] for name in ACCENTS}
    # Monitor places its own translucent count pill on top of the sidebar
    # selection. Start its fill at the outer surface to keep that stack legible.
    sidebar = {name: blend(surface_roles["surfaceContainerLowest"], fill, .55)
               for name, fill in selections.items()}
    surfaces_and_fills = (*surface_roles.values(), *selections.values(), warning)
    text_backgrounds = (page, low, raised, high, *selections.values(), warning)

    def action(anchor, backgrounds, sidebar_fills):
        # Action labels, including app-local counter pills and destructive
        # outlined buttons. Monitor's count pills have a stronger 16% fill.
        return fit_tone(anchor, mode, lambda color:
                        all(contrast(color, bg) >= TEXT for bg in backgrounds)
                        and all(contrast(color, blend(bg, color, .16)) >= TEXT
                                for bg in (page, *sidebar_fills))
                        and contrast(color, blend(low, color, .14)) >= TEXT
                        and all(contrast(color, blend(bg, color, BUTTON_INK)) >= TEXT
                                for bg in (page, low, raised)))

    canonical = anchors(family, mode)
    primaries = {name: action(canonical[name], text_backgrounds, (sidebar[name],))
                 for name in ACCENTS}
    primary = primaries[accent]
    error = action(semantic.colors["failure"], text_backgrounds, sidebar.values())
    # Flutter paints text selection behind the glyphs. The primary itself
    # still has a separate 3:1 requirement as the caret and focus indicator.
    selected_text_backgrounds = [blend(bg, color, .4) for bg in (page, low, raised)
                                 for color in primaries.values()]
    on_surface = fit_tone(foreground, mode, lambda color:
                          all(contrast(color, bg) >= TEXT for bg in surfaces_and_fills)
                          and all(contrast(color, blend(bg, color, BUTTON_INK)) >= TEXT
                                  for bg in text_backgrounds)
                          and all(contrast(color, bg) >= TEXT for bg in selected_text_backgrounds))
    on_variant = fit_tone(quiet, mode, lambda color:
                          contrast(color, highest) >= TEXT
                          and all(contrast(color, blend(bg, color, .12)) >= TEXT
                                  for bg in text_backgrounds))
    outline = readable(GRAY, mode, text_backgrounds + (highest,))
    neutral_edge = blend(page, GRAY, .46 if mode == "dark" else .42)
    roles = dict(surface_roles, onSurface=on_surface, onSurfaceVariant=on_variant,
                 outline=outline, outlineVariant=neutral_edge)
    dark_anchors = anchors(family, "dark")
    light_anchors = anchors(family, "light")
    for role, hue, anchor in (
        ("primary", accent, primary),
        ("secondary", "orange", semantic.colors["warning"]),
        ("tertiary", "purple", semantic.colors["specialized"]),
        ("error", "red", error),
    ):
        title = role.capitalize()
        state_ink = BUTTON_INK if role == "primary" else 0
        roles[role], roles[f"on{title}"] = fill_pair(anchor, mode, ink=state_ink)
        container = semantic.fills[hue]
        roles[f"{role}Container"] = container
        # Selected segments may add a sub-tab layer and widget-local ink.
        container_ink = .21 if role == "primary" else BUTTON_INK
        roles[f"on{title}Container"] = readable(
            canonical[hue], mode, (container,), ink=container_ink
        )
        if role != "error":
            fixed_dim = readable(dark_anchors[hue], "dark", (DEEP_INK,))
            fixed = lighter(fixed_dim, .10)
            roles.update({
                f"{role}Fixed": fixed, f"{role}FixedDim": fixed_dim,
                f"on{title}Fixed": DEEP_INK,
                f"on{title}FixedVariant": readable(light_anchors[hue], "light", (fixed, fixed_dim)),
            })

    inverse_mode = "light" if mode == "dark" else "dark"
    inverse = on_surface
    roles.update(
        inverseSurface=inverse,
        onInverseSurface=page,
        inversePrimary=readable(anchors(family, inverse_mode)[accent], inverse_mode, (inverse,)),
        shadow="000000", scrim="000000", surfaceTint=0,
    )
    tooltip, tooltip_ink = fill_pair(semantic.colors["attention"], mode)
    progress = readable(semantic.accent, mode, (selections[accent], page, low, high), minimum=GRAPHIC)
    info = readable(semantic.colors["information"], mode, (page, low, raised),
                    minimum=GRAPHIC, ink=BUTTON_INK)
    error_border = readable(semantic.colors["failure"], mode, (page, low, raised), minimum=GRAPHIC)
    return roles, {
        "search": {"iconColor": argb(info)},
        "input": {"errorBorderColor": argb(error_border)},
        "sidebar": {"selectedColor": argb(sidebar[accent])},
        "tooltip": {"backgroundColor": argb(tooltip), "textColor": argb(tooltip_ink)},
        "slider": {"activeTrackColor": argb(progress), "thumbColor": argb(progress)},
        "progress": {"color": argb(progress)},
    }


def component_tables(family, level, accent):
    border = {"borderColor": "outlineVariant", "borderWidth": 1}
    field_border = {"borderColor": "outline", "borderWidth": 1}
    focus = {"borderColor": "primary", "borderWidth": 2}
    components = {
        "card": dict(border, backgroundColor="surfaceContainerLow", radius=12),
        "tile": {"selectedTileColor": "primaryContainer", "selectedColor": "onPrimaryContainer", "radius": 8},
        "button": {"radius": 10, "elevation": 0, "surfaceTintColor": 0},
        "outlinedButton": {"radius": 10, "focused": focus},
        "textButton": {"radius": 8, "focused": focus},
        "iconButton": {"radius": 8, "focused": focus},
        "input": dict(field_border, filled=True, fillColor="surfaceContainerLow", radius=8,
                      focusedBorderColor="primary", disabledBorderColor="outlineVariant"),
        "search": dict(field_border, backgroundColor="surfaceContainerLow", radius=10,
                       textColor="onSurface", hintColor="onSurfaceVariant"),
        "appBar": {"backgroundColor": "surface", "iconColor": "onSurfaceVariant"},
        "navigation": {
            "backgroundColor": "surfaceContainerLow", "indicatorColor": "primaryContainer",
            "indicatorRadius": 10, "selectedIconColor": "onPrimaryContainer",
            "selectedLabelColor": "primary", "unselectedIconColor": "onSurfaceVariant",
            "unselectedLabelColor": "onSurfaceVariant", "elevation": 0,
        },
        "segmented": {"radius": 8},
        "sidebar": {"backgroundColor": "surface", "selectedTextColor": "onPrimaryContainer",
                    "selectedIconColor": "onPrimaryContainer", "radius": 8},
        "dialog": dict(border, backgroundColor="surfaceContainer", radius=16),
        "sheet": {"backgroundColor": "surfaceContainer", "radius": 16, "dragHandleColor": "outline"},
        "menu": dict(border, backgroundColor="surfaceContainerHigh", textColor="onSurface", radius=8),
        "tooltip": {"radius": 6},
        "toast": {"backgroundColor": "inverseSurface", "textColor": "onInverseSurface", "radius": 10},
        "slider": {"inactiveTrackColor": "primaryContainer"},
        "progress": {"trackColor": "primaryContainer"},
        "badge": {"backgroundColor": "tertiary", "textColor": "onTertiary"},
        "chip": {"backgroundColor": "surfaceContainerLow", "selectedColor": "secondaryContainer", "radius": 8},
        "divider": {"color": "outlineVariant", "thickness": 1},
        "scrollbar": {"thumbColor": "outline", "trackColor": "surfaceContainerLow", "radius": 4},
    }
    palettes = {}
    for mode in MODES:
        palettes[mode], components[mode] = component_palette(family, level, mode, accent)
    return {mode: {role: argb(color) for role, color in palette.items()}
            for mode, palette in palettes.items()}, components


@cache
def seed_color(family, accent):
    # ServerBox also draws the shared light/dark seed directly on file rows.
    # Pick the best compromise for those consumers without overriding a role.
    backgrounds = []
    for mode in MODES:
        for level in LEVELS if family == "material" else ("medium",):
            roles, _, _ = surfaces(family, level, mode)
            low = roles["surfaceContainerLow"]
            warning = semantic_palette(family, level, mode, accent).fills["orange"]
            backgrounds.extend((roles["surface"], low, blend(low, warning, .55),
                                blend(low, "7D7D7D", 37 / 255)))
    dark, light = (anchors(family, mode)[accent] for mode in MODES)
    return max((blend(dark, light, step / 200) for step in range(201)),
               key=lambda color: min(contrast(color, bg) for bg in backgrounds))


# xterm TerminalTheme. ANSI indexed colors also paint SGR backgrounds.
ANSI = {
    "red": "failure", "green": "success", "yellow": "attention", "blue": "information",
    "magenta": "specialized", "cyan": "network",
}
def terminal_palette(family, level, mode):
    dark = mode == "dark"
    semantic = semantic_palette(family, level, mode, "green")
    background = BG0[mode][level]
    _, foreground, _ = surfaces(family, level, mode)
    selection = semantic.colors["information"]
    selection_alpha = 44 / 255
    selected_bg = blend(background, selection, selection_alpha)

    def text_on_terminal(color):
        # This xterm paints selection on top of both cells and glyphs.
        return (
            contrast(color, background) >= TEXT
            and contrast(blend(color, selection, selection_alpha), selected_bg) >= TEXT
        )

    ansi = {"black": DEEP_INK}
    bright = {"brightBlack": fit_tone(GRAY, mode, text_on_terminal)}
    for slot, use in ANSI.items():
        anchor = semantic.colors[use]
        alt = ORIGINAL_NEUTRAL[SEMANTIC_HUES[use]] if family == "original" else anchor
        normal_anchor, bright_anchor = (alt, anchor) if dark else (anchor, alt)
        normal = fit_tone(normal_anchor, mode, text_on_terminal)
        ansi[slot] = normal
        bright["bright" + slot.title()] = fit_tone(bright_anchor, mode, lambda color:
                                                  text_on_terminal(color)
                                                  and contrast(color, normal) >= 1.14
                                                  and (luminance(color) > luminance(normal)) == dark)

    ansi["white"] = LIGHT_NEUTRALS[0]
    bright["brightWhite"] = PALE_INK
    foreground = fit_tone(foreground, mode, text_on_terminal)
    key_backgrounds = (background, blend(background, foreground, BUTTON_INK))
    accent = readable(semantic.colors["information"], mode, key_backgrounds)
    hits = [fill_pair(anchors(family, "dark")[hue], "dark")[0] for hue in ("yellow", "orange")]
    return {
        "foreground": argb(foreground), "background": argb(background),
        # The xterm block cursor draws on top of glyphs, just as selection does.
        "cursor": argb(foreground, 192), "selection": argb(selection, 44),
        "selectionCursor": argb(accent),
        "searchHitForeground": argb(DEEP_INK),
        "searchHitBackground": argb(hits[0]), "searchHitBackgroundCurrent": argb(hits[1]),
        **{name: argb(color) for name, color in (ansi | bright).items()},
    }


def argb(color, alpha=255):
    return (alpha << 24) | int(color, 16) if isinstance(color, str) else color


def literal(value):
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (str, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def toml_tables(mapping, prefix=""):
    """Write leaf values, then nested tables in insertion order."""
    leaves = {key: value for key, value in mapping.items() if not isinstance(value, dict)}
    if prefix and (leaves or not mapping):
        yield f"\n[{prefix}]\n"
    for key, value in leaves.items():
        is_color = ".palette." in f".{prefix}" or key == "seed" or key.endswith("Color") or (
            prefix.startswith(("components", "variants")) and key == "color"
        )
        encoded = f"0x{value:08X}" if type(value) is int and is_color else literal(value)
        yield f"{key} = {encoded}\n"
    for key, value in mapping.items():
        if isinstance(value, dict):
            yield from toml_tables(value, f"{prefix}.{key}" if prefix else key)


def differences(base, variant):
    delta = {}
    for key, value in variant.items():
        inherited = base.get(key)
        if isinstance(value, dict):
            if changed := differences(inherited or {}, value):
                delta[key] = changed
        elif value != inherited:
            delta[key] = value
    return delta


def appearance(family, level, accent):
    colors, components = component_tables(family, level, accent)
    return {
        "colors": {"seed": argb(seed_color(family, accent)), "palette": colors},
        "components": components,
    }


def manifest(family):
    name = FAMILIES[family]
    theme_id = "milesclem." + name.lower().replace(" ", "-")
    base = appearance(family, "medium", "green")
    variants = {}
    for level in LEVELS if family == "material" else ("medium",):
        for accent in ACCENTS:
            key = f"{level}_{accent}" if family == "material" else accent
            label = key.replace("_", " ").title()
            variants[key] = {"name": label, **differences(base, appearance(family, level, accent))}
    document = {
        "id": theme_id, "name": name, "modes": ["light", "dark"],
        "schema": {"min": 3, "max": 4},
        "colors": {"mode": 0, "systemColor": False, **base["colors"]},
        "components": base["components"],
        "variants": variants,
    }
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    heading = "Gruvbox Original" if family == "original" else name
    notice = notices.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0].strip()
    license_lines = [line for line in notice.splitlines() if not line.startswith("Source: ")]
    header = f"#:schema {SCHEMA_URL}\n" + "\n".join(f"# {line}" if line else "#" for line in license_lines).strip()
    header += "\n\n# Copyright (c) 2026 milesclem contributors (ServerBox adaptation).\n"
    header += "# The adaptation is licensed under the MIT permission and warranty terms above.\n"
    header += "# Regenerate with tools/generate.py.\n"
    return ROOT / "themes" / theme_id / "manifest.toml", header + "".join(toml_tables(document))


def terminal_specification():
    def hex_argb(palette):
        return {name: f"0x{value:08X}" for name, value in palette.items()}

    document = {
        "generatedBy": "tools/generate.py",
        "profiles": {
            family: {
                level: {mode: hex_argb(terminal_palette(family, level, mode)) for mode in MODES}
                for level in LEVELS
            }
            for family in FAMILIES
        },
        "resourceAnchors": {
            family: {
                mode: {name: f"#{value}" for name, value in
                       semantic_palette(family, "medium", mode, "green").resources.items()}
                for mode in MODES
            }
            for family in FAMILIES
        },
    }
    return ROOT / "docs" / "terminal-palettes.json", json.dumps(document, indent=2) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check committed generated bytes")
    args = parser.parse_args()
    files = [*(manifest(family) for family in FAMILIES), terminal_specification()]
    for path, content in files:
        expected = content.encode("utf-8")
        if path.exists() and path.read_bytes() == expected:
            continue
        if args.check:
            parser.exit(1, f"{path.relative_to(ROOT)} is stale. Run tools/generate.py.\n")
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
            temporary.write(expected)
        staged = Path(temporary.name)
        try:
            staged.chmod(0o644)
            staged.replace(path)
        finally:
            staged.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Resolve the manifests and measure source-derived color pairs independently."""
from __future__ import annotations

import argparse
from colorsys import rgb_to_hls
from dataclasses import dataclass
import hashlib
from itertools import product
import json
import math
from pathlib import Path
import re
import tomllib
from urllib.parse import urlparse
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_BLOB = "174e1d7bff0b825ddd00d79fe95f7abfc8f5685e"
TEXT = 4.5
GRAPHIC = 3.0
VARIANTS = {
    "milesclem.gruvbox": ("green", "blue"),
    "milesclem.gruvbox-material": (
        "medium_green", "medium_blue", "hard_green", "hard_blue", "soft_green", "soft_blue",
    ),
}
BG0 = {
    "medium": {"dark": 0xFF282828, "light": 0xFFFBF1C7},
    "hard": {"dark": 0xFF1D2021, "light": 0xFFF9F5D7},
    "soft": {"dark": 0xFF32302F, "light": 0xFFF2E5BC},
}
LADDER = (
    "surfaceContainerLowest", "surfaceContainerLow", "surfaceContainer",
    "surfaceContainerHigh", "surfaceContainerHighest",
)
SURFACES = ("surface", "surfaceDim", "surfaceBright", *LADDER)
TONES = ("primary", "secondary", "tertiary", "error")
# Independent reference anchors for checking the direction of contrast adjustment.
ANCHORS = {
    ("original", "dark"): "FB4934 FE8019 FABD2F B8BB26 8EC07C 83A598 D3869B",
    ("original", "light"): "9D0006 AF3A03 B57614 79740E 427B58 076678 8F3F71",
    ("material", "dark"): "EA6962 E78A4E D8A657 A9B665 89B482 7DAEA3 D3869B",
    ("material", "light"): "C14A4A C35E0A B47109 6C782E 4C7A5D 45707A 945E80",
}
ROLES = {
    *SURFACES, "onSurface", "onSurfaceVariant", "outline", "outlineVariant",
    "shadow", "scrim", "inverseSurface", "onInverseSurface", "inversePrimary", "surfaceTint",
    *(tone + suffix for tone in TONES for suffix in ("", "Container")),
    *("on" + tone.title() + suffix for tone in TONES for suffix in ("", "Container")),
    *(tone + suffix for tone in TONES[:-1] for suffix in ("Fixed", "FixedDim")),
    *("on" + tone.title() + suffix for tone in TONES[:-1] for suffix in ("Fixed", "FixedVariant")),
}
# Local FSBT projection for a dependency-free audit. The release check also
# requires validation against the whole official schema.
SHAPE = 'radius:ratio borderColor:color borderWidth:borderWidth'
SURFACE = 'backgroundColor:color elevation:elevation shadowColor:color surfaceTintColor:color'
BUTTON = f'{SHAPE} {SURFACE} foregroundColor:color overlayColor:color padding:inset minHeight:size'
STATES = {'disabled','pressed','hovered','focused','selected'}
STATEFUL = {'button','textButton','outlinedButton','iconButton'}
FIELDS = {
    'card': f'{SHAPE} {SURFACE} margin:inset',
    'tile': f'{SHAPE} backgroundColor:color selectedTileColor:color textColor:color iconColor:color selectedColor:color padding:inset',
    'button': BUTTON, 'textButton': BUTTON, 'outlinedButton': BUTTON,
    'iconButton': BUTTON+' iconSize:size',
    'input': f'{SHAPE} filled:flag fillColor:color focusedBorderColor:color errorBorderColor:color disabledBorderColor:color padding:inset',
    'search': f'{SHAPE} backgroundColor:color elevation:elevation iconColor:color textColor:color hintColor:color height:size padding:inset',
    'navigation': 'backgroundColor:color indicatorColor:color indicatorRadius:ratio selectedIconColor:color unselectedIconColor:color selectedLabelColor:color unselectedLabelColor:color elevation:elevation',
    'appBar': f'{SURFACE} foregroundColor:color titleColor:color iconColor:color',
    'segmented': f'{SHAPE} backgroundColor:color selectedColor:color textColor:color selectedTextColor:color',
    'sidebar': 'backgroundColor:color selectedColor:color textColor:color selectedTextColor:color iconColor:color selectedIconColor:color radius:ratio padding:inset',
    'dialog': f'{SHAPE} {SURFACE} barrierColor:color insetPadding:inset',
    'sheet': f'{SHAPE} {SURFACE} barrierColor:color dragHandleColor:color',
    'menu': f'{SHAPE} {SURFACE} textColor:color',
    'tooltip': f'{SHAPE} backgroundColor:color textColor:color padding:inset',
    'toast': f'{SHAPE} backgroundColor:color textColor:color elevation:elevation',
    'switch': 'thumbColor:color trackColor:color trackOutlineColor:color selectedThumbColor:color selectedTrackColor:color selectedTrackOutlineColor:color',
    'slider': 'activeTrackColor:color inactiveTrackColor:color thumbColor:color overlayColor:color trackHeight:thickness',
    'progress': 'color:color trackColor:color thickness:thickness radius:ratio',
    'badge': 'backgroundColor:color textColor:color smallSize:size largeSize:size',
    'chip': f'{SHAPE} backgroundColor:color selectedColor:color textColor:color padding:inset',
    'divider': 'color:color thickness:thickness',
    'scrollbar': 'thumbColor:color trackColor:color radius:ratio thickness:thickness',
}
FIELDS = {k:dict(x.split(':') for x in v.split()) for k,v in FIELDS.items()}
BOUNDS = {'ratio':40,'borderWidth':8,'elevation':24,'size':96,'thickness':16}
STATE_PRIORITY = ("selected", "focused", "hovered", "pressed", "disabled")
ACTIVE_STATES = (
    frozenset(), {"hovered"}, {"focused"}, {"pressed"},
    {"focused", "hovered"}, {"focused", "pressed"},
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return tomllib.loads(path.read_text(encoding="utf-8"))


def argb(value):
    return type(value) is int and 0 <= value <= 0xFFFFFFFF


def valid_field(kind, value):
    if kind == "color":
        return argb(value) or isinstance(value, str) and value in ROLES
    if kind == "flag":
        return type(value) is bool
    if kind == "inset":
        return (isinstance(value, list) and len(value) == 4
                and all(type(part) in (int, float) and 0 <= part <= 64 for part in value))
    return type(value) in (int, float) and 0 <= value <= BOUNDS[kind]


def check_components(components, path="components", allow_brightness=True):
    require(isinstance(components, dict), path)
    for name, fields in components.items():
        location = f"{path}.{name}"
        if allow_brightness and name in ("dark", "light"):
            check_components(fields, location, allow_brightness=False)
            continue
        require(name in FIELDS and isinstance(fields, dict), location)
        for field, value in fields.items():
            if field in STATES and name in STATEFUL:
                require(isinstance(value, dict), f"{location}.{field}")
                for key, state_value in value.items():
                    require(key in FIELDS[name] and valid_field(FIELDS[name][key], state_value),
                            f"{location}.{field}.{key}")
            else:
                require(field in FIELDS[name] and valid_field(FIELDS[name][field], value),
                        f"{location}.{field}")


def check_colors(colors):
    require(set(colors) <= {"mode", "seed", "systemColor", "palette"}, "unknown colors field")
    if "mode" in colors:
        require(type(colors["mode"]) is int and 0 <= colors["mode"] <= 2, "colors.mode")
    if "seed" in colors:
        require(argb(colors["seed"]), "colors.seed")
    if "systemColor" in colors:
        require(type(colors["systemColor"]) is bool, "colors.systemColor")
    palettes = colors.get("palette", {})
    require(set(palettes) <= {"dark", "light"}, "unknown palette brightness")
    for palette in palettes.values():
        require(set(palette) <= ROLES and all(map(argb, palette.values())), "palette")


def merge(base, overrides):
    """FSBT deep-merges tables and replaces scalars before brightness lookup."""
    result = dict(base)
    for key, value in overrides.items():
        inherited = result.get(key)
        if isinstance(value, dict) and isinstance(inherited, dict):
            result[key] = merge(inherited, value)
        else:
            result[key] = value
    return result


def component_styles(components, mode):
    common = {key: value for key, value in components.items() if key not in ("dark", "light")}
    return merge(common, components.get(mode, {}))


def active_style(style, states):
    effective = {key: value for key, value in style.items() if key not in STATES}
    for state in STATE_PRIORITY:
        if state in states:
            effective.update(style.get(state, {}))
    return effective


def channels(number):
    return tuple((number >> shift & 255) / 255 for shift in (16, 8, 0, 24))


def over(top, bottom):
    alpha = top[3] + bottom[3] * (1 - top[3])
    if not alpha:
        return (0., 0., 0., 0.)
    return tuple((fg * top[3] + bg * bottom[3] * (1 - top[3])) / alpha
                 for fg, bg in zip(top[:3], bottom[:3])) + (alpha,)


def luminance(color):
    linear = (c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in color[:3])
    return sum(weight * value for weight, value in zip((.2126, .7152, .0722), linear))


def contrast(foreground, background):
    require(background[3] == 1, "opaque contrast substrate required")
    low, high = sorted((luminance(over(foreground, background)), luminance(background)))
    return (high + .05) / (low + .05)


def hex_color(color):
    return "#" + "".join(f"{math.floor(value * 255 + .5):02X}" for value in color[:3])


def ink(color, opacity):
    return (*color[:3], opacity)


def check_hue(color, anchor, context):
    h, _, s = rgb_to_hls(*channels(color)[:3])
    reference_h, _, reference_s = rgb_to_hls(*channels(anchor)[:3])
    delta = abs(h - reference_h)
    require(min(delta, 1 - delta) < .035 and s >= reference_s * .75, f"{context}: Gruvbox hue")


def anchors(family, mode):
    names = ("red", "orange", "yellow", "green", "aqua", "blue", "purple")
    return dict(zip(names, (int("FF" + value, 16) for value in ANCHORS[family, mode].split())))


def references():
    require(contrast(channels(0xFFFFFFFF), channels(0xFF000000)) == 21, "contrast oracle")
    require(hex_color(over(channels(0x80FF0000), channels(0xFF0000FF))) == "#80007F",
            "source-over oracle")
    sample = {"iconButton": {"focused": {"borderColor": "primary", "borderWidth": 2}}}
    overrides = {"dark": {"iconButton": {"focused": {"borderColor": "error"}}}}
    style = component_styles(merge(sample, overrides), "dark")["iconButton"]
    style["pressed"] = {"borderWidth": 3, "foregroundColor": "primary"}
    style["disabled"] = {"foregroundColor": "outline"}
    require(active_style(style, {"focused", "pressed", "disabled"}) == {
        "borderColor": "error", "borderWidth": 3, "foregroundColor": "outline",
    }, "brightness and button state inheritance")


def https(value):
    if not isinstance(value, str):
        return False
    url = urlparse(value)
    return url.scheme == "https" and bool(url.netloc)


def listings(require_versions):
    repo = read(ROOT / "repo.toml")
    require(type(repo.get("schema")) is int and repo["schema"] == 1
            and isinstance(repo.get("name"), str) and repo["name"].strip(), "repo metadata")
    themes = ROOT / "themes"
    require({path.stem for path in themes.glob("*.toml")} == set(VARIANTS), "listing IDs")
    require({path.name for path in themes.iterdir() if path.is_dir()} == set(VARIANTS), "package IDs")
    result = {}
    for theme_id in VARIANTS:
        manifest = read(themes / theme_id / "manifest.toml")
        listing = read(themes / f"{theme_id}.toml")
        require(listing.get("id") == theme_id and listing.get("name") == manifest.get("name"),
                f"{theme_id}: listing identity")
        require(listing.get("license") == "MIT" and https(listing.get("homepage")), "license/homepage")
        descriptions = listing.get("description")
        require(isinstance(descriptions, dict) and {"en", "zh", "zh-TW"} <= descriptions.keys()
                and all(isinstance(text, str) and text.strip() for text in descriptions.values()),
                "listing description")
        versions = listing.get("version", [])
        require(isinstance(versions, list) and (versions or not require_versions),
                f"{theme_id}: version array")
        seen = set()
        for release in versions:
            require(isinstance(release, dict), "version table")
            version = release.get("version")
            require(isinstance(version, str) and version not in seen
                    and re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", version), "unique version")
            seen.add(version)
            lo, hi = release.get("schema_min"), release.get("schema_max")
            require(type(lo) is int and type(hi) is int and 1 <= lo <= hi
                    and lo <= 4 and hi >= 3, "version schema")
            digest, size = release.get("sha256"), release.get("size")
            require(isinstance(digest, str) and re.fullmatch("[0-9a-f]{64}", digest)
                    and type(size) is int and 0 < size <= 16 * 1024 * 1024, "version digest/size")
            require("path" not in release and https(release.get("url")), "version URL")
        result[theme_id] = versions
    return result


@dataclass
class Measurements:
    rows: list
    identity: dict
    palette: dict

    def color(self, value):
        return channels(self.palette[value] if isinstance(value, str) else value)

    def pair(self, context, foreground, background, minimum=TEXT, *, layer=None, opacity=None,
             over_glyphs=False, substrate=None, scope="theme"):
        fg, bg = self.color(foreground), self.color(background)
        if substrate is not None:
            bg = over(bg, self.color(substrate))
        if layer is not None:
            overlay = self.color(layer)
            if opacity is not None:
                overlay = ink(overlay, opacity)
            if over_glyphs:
                fg = over(overlay, over(fg, bg))
            bg = over(overlay, bg)
        ratio = contrast(fg, bg)
        self.rows.append({
            **self.identity, "scope": scope, "context": context,
            "foreground": hex_color(over(fg, bg)), "background": hex_color(bg),
            "ratio": round(ratio, 4), "target": minimum, "status": "PASS" if ratio >= minimum else "FAIL",
        })
        return ratio


def state_name(states):
    return "+".join(sorted(states)) or "rest"


def flutter_ink(states):
    # Flutter M3 action buttons choose pressed, then hovered, then focused.
    if "pressed" in states:
        return 26 / 255
    if "hovered" in states:
        return 20 / 255
    return 26 / 255 if "focused" in states else 0


def buttons(measure, components):
    pair = measure.pair
    hosts = ("surface", "surfaceContainerLow", "surfaceContainer")
    specs = (
        ("Filled", "button", "onPrimary", "primary"),
        ("Filled.tonal", "button", "onSecondaryContainer", "secondaryContainer"),
        ("Elevated", "button", "primary", "surfaceContainerLow"),
        ("Outlined", "outlinedButton", "primary", None),
        ("Services Stop", "outlinedButton", "error", None),
        ("TextButton", "textButton", "primary", None),
        ("IconButton", "iconButton", "onSurfaceVariant", None),
        ("IconButton selected", "iconButton", "primary", None),
    )
    for label, component, fg, fill in specs:
        for bg in (fill,) if fill else hosts:
            minimum = GRAPHIC if component == "iconButton" else TEXT
            for state in ACTIVE_STATES:
                active = state | {"selected"} if label.endswith(" selected") else state
                style = active_style(components[component], active)
                alpha = flutter_ink(active)
                overlay = fg if alpha else None
                status = f"{label} {state_name(active)} on {bg}"
                pair(status, style.get("foregroundColor", fg), style.get("backgroundColor", bg),
                     minimum, layer=overlay, opacity=alpha)
                if "focused" in active and "borderColor" in style:
                    pair(f"{status} focus ring", style["borderColor"], bg, GRAPHIC,
                         layer=overlay, opacity=alpha)
            # Material keeps disabled labels at 38% and filled surfaces at 12%.
            disabled_ink = ink(measure.color("onSurface"), .38)
            substrate = measure.color("surface" if fill else bg)
            disabled_fill = over(ink(measure.color("onSurface"), .12), substrate) if component == "button" else substrate
            require(contrast(disabled_ink, disabled_fill) < contrast(measure.color(fg), measure.color(bg)),
                    f"{label}: disabled affordance")


def measure_components(measure, components, seed):
    p = measure.palette
    pair = measure.pair
    page, card, raised, high, highest = "surface", *LADDER[1:]
    selected = "primaryContainer"
    warning = "secondaryContainer"

    def style(name, field, fallback):
        return components.get(name, {}).get(field, fallback)

    for background in SURFACES:
        for foreground in ("onSurface", "onSurfaceVariant"):
            pair(f"{foreground} on {background}", foreground, background)
    for role in TONES:
        foreground = f"on{role.title()}"
        pair(f"{role} filled", foreground, role)
        pair(f"{role} container", f"{foreground}Container", f"{role}Container")
        if role != "error":
            for background in (f"{role}Fixed", f"{role}FixedDim"):
                for text in (f"{foreground}Fixed", f"{foreground}FixedVariant"):
                    pair(f"{text} on {background}", text, background)
    pair("inverse body", "onInverseSurface", "inverseSurface")
    pair("inverse action", "inversePrimary", "inverseSurface")

    card_bg = style("card", "backgroundColor", card)
    pair("card body", "onSurface", card_bg)
    pair("card subtitle", "onSurfaceVariant", card_bg)
    appbar = style("appBar", "backgroundColor", page)
    pair("AppBar title", style("appBar", "titleColor", "onSurface"), appbar)
    pair("AppBar foreground", style("appBar", "foregroundColor", "onSurface"), appbar)
    pair("AppBar icon", style("appBar", "iconColor", "onSurface"), appbar, GRAPHIC)

    nav_bg = style("navigation", "backgroundColor", raised)
    nav_selected = style("navigation", "indicatorColor", warning)
    sidebar_bg = style("sidebar", "backgroundColor", card_bg)
    sidebar_selected = style("sidebar", "selectedColor", selected)
    tile_selected = style("tile", "selectedTileColor", selected)
    for state in ("selected", "unselected"):
        nav_fg = "onPrimaryContainer" if state == "selected" else "onSurfaceVariant"
        bg = nav_selected if state == "selected" else nav_bg
        pair(f"navigation {state} icon", style("navigation", f"{state}IconColor", nav_fg), bg, GRAPHIC)
        pair(f"navigation {state} label", style("navigation", f"{state}LabelColor", "onSurface"), nav_bg)
    pair("sidebar selected text", style("sidebar", "selectedTextColor", "onPrimaryContainer"), sidebar_selected)
    pair("sidebar selected icon", style("sidebar", "selectedIconColor", "primary"), sidebar_selected, GRAPHIC)
    pair("sidebar title", style("sidebar", "textColor", "onSurface"), sidebar_bg)
    pair("sidebar icon", style("sidebar", "iconColor", "onSurfaceVariant"), sidebar_bg, GRAPHIC)
    pair("sidebar live mark", "primary", sidebar_selected, GRAPHIC)
    pair("selected tile foreground", style("tile", "selectedColor", "primary"), tile_selected)
    pair("selected tile subtitle", "onSurfaceVariant", tile_selected)
    pair("selected tile native title style", "onSurface", tile_selected)
    for label, bg, fill in (("navigation", nav_bg, nav_selected), ("sidebar", sidebar_bg, sidebar_selected),
                            ("list tile", card_bg, tile_selected), ("segmented tabs", raised, selected)):
        pair(f"{label} selected fill alone", fill, bg, GRAPHIC, scope="visual_cue")

    field = style("input", "fillColor", card)
    for host in (page, field, raised):
        pair("field text", "onSurface", host)
        pair("field hint", "onSurfaceVariant", host)
        pair("field hover hint", "onSurfaceVariant", host, layer="onSurface", opacity=.08)
        pair("selected field text (Material)", "onSurface", host, layer="primary", opacity=.40)
        pair("field caret and selection handle", "primary", host, GRAPHIC)
        pair("error helper text", "error", host)
        for label, prop, fallback in (
            ("rest", "borderColor", "outline"), ("focus", "focusedBorderColor", "primary"),
            ("error/focused error", "errorBorderColor", "error"),
        ):
            pair(f"input {label} border", style("input", prop, fallback), host, GRAPHIC)
        disabled = measure.color(style("input", "disabledBorderColor", "outlineVariant"))
        enabled = measure.color(style("input", "borderColor", "outline"))
        require(contrast(disabled, measure.color(host)) < contrast(enabled, measure.color(host)),
                "disabled field border is subdued")
    search = style("search", "backgroundColor", card)
    for background in (search, appbar):
        pair("search text", style("search", "textColor", "onSurface"), background)
        pair("search placeholder", style("search", "hintColor", "onSurfaceVariant"), background)
        pair("search icon", style("search", "iconColor", "onSurfaceVariant"), background, GRAPHIC)
    pair("search field border", style("search", "borderColor", "outline"), search, GRAPHIC)

    for component, default in (("dialog", raised), ("sheet", raised), ("menu", high)):
        bg = style(component, "backgroundColor", default)
        pair(f"{component} title", "onSurface", bg)
        pair(f"{component} body", "onSurfaceVariant", bg)
    menu = style("menu", "backgroundColor", high)
    pair("popup menu entry", style("menu", "textColor", "onSurface"), menu)
    for opacity in (20 / 255, 26 / 255):
        pair("Material menu action hover/focus", "onSurface", menu, layer="onSurface", opacity=opacity)
    pair("sheet grip", style("sheet", "dragHandleColor", "outline"), style("sheet", "backgroundColor", raised), GRAPHIC)
    for component, background, text in (
        ("tooltip", "inverseSurface", "onInverseSurface"),
        ("toast", "inverseSurface", "onInverseSurface"),
        ("badge", "error", "onError"),
    ):
        pair(component, style(component, "textColor", text), style(component, "backgroundColor", background))

    for state in ACTIVE_STATES:
        alpha = flutter_ink(state)
        label = state_name(state)
        for title, fg, bg in (
            ("native TabBar selected", "primary", page),
            ("native TabBar unselected", "onSurfaceVariant", page),
            ("native segment selected", "onSecondaryContainer", warning),
            ("native segment unselected", "onSurface", raised),
            ("shared tab selected", "onPrimaryContainer", selected),
            ("shared tab unselected", "onSurfaceVariant", raised),
        ):
            pair(f"{title} {label}", fg, bg, layer=fg if alpha else None, opacity=alpha)
    pair("nested selected shared tab label", "onPrimaryContainer", selected,
         layer="onPrimaryContainer", opacity=1 - .88 * .90)
    pair("native tab indicator", "primary", page, GRAPHIC)

    chip_bg = style("chip", "backgroundColor", card)
    chip_selected = style("chip", "selectedColor", warning)
    for state in ACTIVE_STATES:
        for label, bg, fg in (("regular", chip_bg, "onSurfaceVariant"),
                              ("selected", chip_selected, "onSecondaryContainer")):
            alpha = flutter_ink(state)
            pair(f"chip {label} {state_name(state)}", style("chip", "textColor", fg), bg,
                 layer=fg if alpha else None, opacity=alpha)
    # The shared selected chip fill also reaches chip variants with a neutral label.
    pair("selected chip neutral label", "onSurfaceVariant", chip_selected)

    for component, active_name, track_name in (
        ("slider", "activeTrackColor", "inactiveTrackColor"), ("progress", "color", "trackColor"),
    ):
        fill, track = style(component, active_name, "primary"), style(component, track_name, selected)
        pair(f"{component} active track", fill, track, GRAPHIC)
        pair(f"{component} active on card", fill, card_bg, GRAPHIC)
    pair("slider thumb against track", style("slider", "thumbColor", "primary"),
         style("slider", "inactiveTrackColor", selected), GRAPHIC)
    pair("slider thumb on card", style("slider", "thumbColor", "primary"), card_bg, GRAPHIC)
    pair("switch selected thumb", "onPrimary", "primary", GRAPHIC)
    pair("switch selected thumb while interacting", selected, "primary", GRAPHIC)
    pair("switch inactive thumb", "outline", highest, GRAPHIC)
    pair("switch inactive thumb while interacting", "onSurfaceVariant", highest, GRAPHIC)
    for bg in (style("scrollbar", "trackColor", card), page, card_bg):
        pair("scrollbar thumb", style("scrollbar", "thumbColor", "outline"), bg, GRAPHIC)
    require(p["outlineVariant"] != p["surface"], "decorative separators must remain visible")

    buttons(measure, components)
    for fg in ("primary", "error"):
        for bg in (page, card_bg, raised, high, warning):
            pair(f"app-local {fg} label on {bg}", fg, bg)
        for bg in (sidebar_bg, sidebar_selected):
            pair(f"Monitor rail {fg} count pill", fg, bg, layer=fg, opacity=.16)
        pair(f"Monitor {fg} tag", fg, card_bg, layer=fg, opacity=.14)
    pair("Workspace target", "primary", page, layer="primary", opacity=.08)
    pair("Monitor Desk helper", "outline", card_bg)
    pair("selected metric note or label", "onSecondaryContainer", warning)
    pair("selected file row text", "onSurface", card_bg, layer=warning, opacity=.55)

    for bg in (page, card_bg):
        pair("direct shared seed border", seed, bg, GRAPHIC, scope="upstream")
    pair("file row focus border uses the shared seed", seed, card_bg, GRAPHIC,
         layer=warning, opacity=.55, scope="upstream")
    pair("disk track uses the shared seed", seed, card_bg, GRAPHIC,
         layer=0xFF7D7D7D, opacity=37 / 255, scope="upstream")
    for bg in (page, raised):
        for label, color in (("red", 0xFFF44336), ("green", 0xFF4CAF50),
                             ("grey", 0xFF757575 if bg == page else 0xFF9E9E9E)):
            pair(f"connection statistics {label}", color, bg, scope="upstream")
    pair("connection statistics orange success rate", 0xFFFF9800, page, scope="upstream")
    pair("Monitor connected icon hardcodes Material green", 0xFF4CAF50, card_bg, GRAPHIC, scope="upstream")
    pair("Monitor restart notice hardcodes Material orange", 0xFFFF9800, card_bg, scope="upstream")


ANSI = ("black", "red", "green", "yellow", "blue", "magenta", "cyan", "white")
BRIGHT = tuple("bright" + name.title() for name in ANSI)
TERMINAL_FIELDS = {
    "foreground", "background", "cursor", "selection", "selectionCursor", "searchHitForeground",
    "searchHitBackground", "searchHitBackgroundCurrent", *ANSI, *BRIGHT,
}


def profiles(rows):
    raw = json.loads((ROOT / "docs/terminal-palettes.json").read_text(encoding="utf-8"))
    profiles = raw["profiles"]
    require(set(profiles) == {"original", "material"}, "terminal families")
    for family, levels in profiles.items():
        require(set(levels) == set(BG0), f"{family}: terminal contrast levels")
        for level, modes in levels.items():
            require(set(modes) == {"dark", "light"}, "terminal modes")
            for mode, palette in modes.items():
                require(set(palette) == TERMINAL_FIELDS
                        and all(re.fullmatch(r"0x[0-9A-F]{8}", color) for color in palette.values()),
                        "terminal theme fields and ARGB")
                palette = {key: int(value, 16) for key, value in palette.items()}
                modes[mode] = palette
                require(palette["background"] == BG0[level][mode], "terminal bg0")
                overlays = {"cursor", "selection"}
                require(all(color >> 24 == 255 for name, color in palette.items() if name not in overlays),
                        "ANSI and terminal inks must be opaque")
                require(all(0 < palette[name] >> 24 < 255 for name in overlays), "translucent glyph overlays")
                require(len({palette[name] for name in (*ANSI, *BRIGHT)}) == 16, "distinct ANSI entries")

                measure = Measurements(rows, {"family": family, "level": level, "mode": mode}, palette)
                canonical = anchors(family, mode)
                resources = {"cpu": "yellow", "memory": "purple", "disk": "orange", "network": "aqua"}
                require(raw["resourceAnchors"][family][mode] == {
                    resource: f"#{canonical[hue] & 0xFFFFFF:06X}" for resource, hue in resources.items()
                }, "resource anchors")
                chromatic = (*ANSI[1:7], *BRIGHT[1:7])
                for name in ("foreground", "brightBlack", *chromatic):
                    measure.pair(f"terminal {name}", name, "background")
                    measure.pair(f"selected terminal {name}", name, "background",
                                 layer="selection", over_glyphs=True)
                for normal, bright in zip(ANSI[1:7], BRIGHT[1:7]):
                    pair_order = luminance(measure.color(bright)) > luminance(measure.color(normal))
                    require(pair_order == (mode == "dark"), f"ANSI intensity direction for {normal}")
                    measure.pair(f"ANSI normal/bright distinction {normal}", bright, normal, 1.12)
                for slot in (*ANSI, *BRIGHT):
                    neutral = max(("black", "brightWhite"),
                                  key=lambda name: contrast(measure.color(name), measure.color(slot)))
                    measure.pair(f"ANSI background {slot} with {neutral}", neutral, slot)
                # Literal black/white remain available to applications that paint ANSI backgrounds.
                for name in ("white", "brightWhite"):
                    measure.pair(f"ANSI black on {name}", "black", name)
                    measure.pair(f"ANSI {name} on black", name, "black")
                neutral_ink = "black" if mode == "light" else "white"
                measure.pair(f"ordinary ANSI neutral ({neutral_ink})", neutral_ink, "background")
                measure.pair("terminal cursor", "cursor", "background", GRAPHIC)
                measure.pair("selected terminal cursor", "cursor", "background", GRAPHIC,
                             layer="selection", over_glyphs=True)
                measure.pair("terminal selection accent", "selectionCursor", "background", GRAPHIC,
                             layer="selection", over_glyphs=True)
                for slot in ("searchHitBackground", "searchHitBackgroundCurrent"):
                    measure.pair(f"terminal {slot}", "searchHitForeground", slot)
                    measure.pair(f"terminal {slot} indicator", slot, "background", GRAPHIC, scope="visual_cue")
    return profiles


def terminals(rows, identity, app, seed, profiles, family, level):
    app_mode = identity["mode"]
    for setting in ("followApp", "light", "dark"):
        mode = app_mode if setting == "followApp" else setting
        appearance = {**identity, "terminal_setting": setting, "terminal_mode": mode}
        stock = {
            "page": app["surface"],
            "background": 0xFF000000 if mode == "dark" else 0xFFFFFFFF,
            "foreground": 0xFFCCCCCC if mode == "dark" else 0xFF000000,
            "key": 0xFFFFFFFF if mode == "dark" else 0xFF000000,
            "armed": seed,
        }
        upstream = Measurements(rows, appearance, stock)
        for surface, background in (("SSH page", "page"), ("floated SSH", "background")):
            for label, fg in (("text", "foreground"), ("key", "key"), ("armed key", "armed")):
                upstream.pair(f"stock {surface} {label}", fg, background, scope="upstream")

        # The separately applicable patch chooses a full xterm theme once.
        # All text and keys in either host share that profile's backdrop.
        patched = Measurements(rows, appearance, profiles[family][level][mode])
        for surface in ("SSH page", "floated SSH"):
            patched.pair(f"profile {surface} text", "foreground", "background")
            for label, fg in (("key", "foreground"), ("armed key", "selectionCursor")):
                for state in ACTIVE_STATES[:4]:
                    alpha = flutter_ink(state)
                    patched.pair(f"profile {surface} {label} {state_name(state)}", fg, "background",
                                 layer="foreground" if alpha else None, opacity=alpha)


def check_variant(palette, components, family, mode, level, accent):
    require(set(palette) == ROLES and palette["surfaceTint"] == 0, "46 explicit roles")
    require(all(color >> 24 == 255 for role, color in palette.items() if role != "surfaceTint"),
            "opaque roles")
    require(palette["surface"] == BG0[level][mode], f"canonical {mode} {level} bg0")
    lightness = [luminance(channels(palette[role])) for role in LADDER]
    require(lightness == sorted(set(lightness), reverse=mode == "light"), "distinct surface ladder")
    for component in STATEFUL:
        for state in (*STATES, "base"):
            values = components[component] if state == "base" else components[component].get(state, {})
            require(not {"backgroundColor", "foregroundColor", "overlayColor"} & values.keys(),
                    f"{component}.{state}: Flutter button pairs and ink")
    require(not components.get("switch") and set(components["segmented"]) == {"radius"}
            and "textColor" not in components["chip"], "stateful native defaults")
    canonical = anchors(family, mode)
    for role, hue in (("primary", accent), ("error", "red"), ("secondary", "orange"), ("tertiary", "purple")):
        check_hue(palette[role], canonical[hue], role)
    for component, field, hue in (
        ("tooltip", "backgroundColor", "yellow"), ("progress", "color", accent),
        ("input", "errorBorderColor", "red"), ("search", "iconColor", "blue"),
    ):
        value = components[component][field]
        check_hue(palette[value] if isinstance(value, str) else value, canonical[hue], component)


def archive(path, output):
    archive_path = output / f"{path.parent.name}-preview.fsbt"
    with zipfile.ZipFile(archive_path) as package:
        require(package.namelist() == ["manifest.toml"] and package.testzip() is None
                and package.read("manifest.toml") == path.read_bytes(), "package bytes and root path")
    data = archive_path.read_bytes()
    return {"name": archive_path.name, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


def validator(path):
    if path is None:
        return None
    raw = path.read_bytes()
    git_blob = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    require(git_blob == SCHEMA_BLOB, "schema must match the reviewed ServerBox Git blob")
    schema = json.loads(raw)
    from jsonschema import validators
    return validators.validator_for(schema)(schema)


def audit(schema, package_dir, published):
    rows, packages = [], []
    terminal = profiles(rows)
    appearances = 0
    for theme_id, keys in VARIANTS.items():
        path = ROOT / "themes" / theme_id / "manifest.toml"
        require(not path.is_symlink() and not path.parent.is_symlink() and path.stat().st_size <= 64 * 1024
                and {file.name for file in path.parent.iterdir()} == {"manifest.toml"}, "package contents")
        manifest = read(path)
        if schema is not None:
            schema.validate(manifest)
        variants = manifest.pop("variants")
        require(list(variants) == list(keys), "manifest variant order")
        family = "material" if theme_id.endswith("-material") else "original"
        name = "Gruvbox Material" if family == "material" else "Gruvbox"
        require(set(manifest) == {"id", "name", "modes", "schema", "colors", "components"}
                and manifest["id"] == theme_id and manifest["name"] == name
                and manifest["modes"] == ["light", "dark"] and manifest["schema"] == {"min": 3, "max": 4},
                "manifest identity and compatibility")
        check_colors(manifest["colors"])
        check_components(manifest["components"])
        seeds, palettes = {}, {}
        for key, variant in variants.items():
            require(set(variant) <= {"name", "colors", "components"}
                    and variant["name"] == key.replace("_", " ").title(), f"variant {key} shape/label")
            overrides = {k: value for k, value in variant.items() if k != "name"}
            check_colors(overrides.get("colors", {}))
            check_components(overrides.get("components", {}))
            effective = merge(manifest, overrides)
            if key == keys[0]:
                require(effective == manifest, "first variant inherits the complete package defaults")
            colors = effective["colors"]
            level, accent = key.split("_") if "_" in key else ("medium", key)
            require(colors["mode"] == 0 and colors["systemColor"] is False, "default System mode")
            seed = colors["seed"]
            require(seed >> 24 == 255 and seeds.setdefault(accent, seed) == seed, "shared seed by accent")
            palettes[key] = colors["palette"]
            for mode, palette in colors["palette"].items():
                components = component_styles(effective["components"], mode)
                check_variant(palette, components, family, mode, level, accent)
                identity = {"id": theme_id, "variant": key, "mode": mode}
                measure_components(Measurements(rows, identity, palette), components, seed)
                terminals(rows, identity, palette, seed, terminal, family, level)
                appearances += 1
            day, night = (colors["palette"][mode] for mode in ("light", "dark"))
            require(all(day[role] == night[role] for role in ROLES if "Fixed" in role), "fixed roles")
        require(seeds["green"] != seeds["blue"], "distinct Green and Blue seed")
        for green, blue in zip(keys[::2], keys[1::2]):
            for mode in ("dark", "light"):
                pg, pb = palettes[green][mode], palettes[blue][mode]
                require(all(pg[role] == pb[role] for role in ROLES if "primary" not in role.lower()),
                        "accent variants retain the same neutral and semantic roles")
                require(pg["primary"] != pb["primary"] and pg["primaryContainer"] != pb["primaryContainer"],
                        "both Green and Blue selections must resolve")
        if package_dir:
            packages.append(archive(path, package_dir))
    require(appearances == 16, "eight variants in both app modes")
    if package_dir:
        require({file.name for file in package_dir.glob("*.fsbt")} == {p["name"] for p in packages},
                "exact preview package set")
    scopes = ("theme", "upstream", "visual_cue")
    counts = {scope: {status: sum(row["scope"] == scope and row["status"] == status for row in rows)
                      for status in ("PASS", "FAIL")} for scope in scopes}
    return {
        "appearances": appearances, "app_terminal_combinations": appearances * 3,
        "terminal_profiles": 12, "counts": counts, "full_official_schema_checked": schema is not None,
        "listing_versions_present": all(published.values()), "packages": packages,
        "requires_runtime": [
            "Android SSH tab and floating SSH, virtual-key states and app/terminal mode changes",
            "Custom SSH image and opacity, drawn ANSI cells, selection handles and tapped keys",
            "Flutter focus, hover, press, disabled appearance and selected cues on real routes",
        ],
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--packages", type=Path)
    parser.add_argument("--require-versions", action="store_true")
    args = parser.parse_args()
    references()
    report = audit(validator(args.schema), args.packages, listings(args.require_versions))
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, indent=2))
    for row in report["rows"]:
        if row["scope"] == "theme" and row["status"] == "FAIL":
            print(json.dumps(row))
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return int(bool(report["counts"]["theme"]["FAIL"]))


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate the two self-contained manifests; no third-party dependencies."""
from pathlib import Path
import json
import os
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SB = 'fa7941a0b3d4dda154cbf85b007dc6348812e679'
SCHEMA_URL = f'https://raw.githubusercontent.com/lollipopkit/flutter_server_box/{SB}/docs/schemas/fsbt-manifest.schema.json'
NAMES = ('red','orange','yellow','green','aqua','blue','purple')
ANCHORS = {
    'original': {'dark': 'FB4934 FE8019 FABD2F B8BB26 8EC07C 83A598 D3869B', 'light': '9D0006 AF3A03 B57614 79740E 427B58 076678 8F3F71'},
    'material': {'dark': 'EA6962 E78A4E D8A657 A9B665 89B482 7DAEA3 D3869B', 'light': 'C14A4A C35E0A B47109 6C782E 4C7A5D 45707A 945E80'},
}
# bg_dim, bg0, bg1, bg2, bg3, bg4, bg5, bg_statusline2.
MATERIAL_BG = {
    ('hard','dark'): '141617 1D2021 282828 282828 3C3836 3C3836 504945 32302F',
    ('medium','dark'): '1B1B1B 282828 32302F 32302F 45403D 45403D 5A524C 3A3735',
    ('soft','dark'): '252423 32302F 3C3836 3C3836 504945 504945 665C54 46413E',
    ('hard','light'): 'F3EAC7 F9F5D7 F5EDCA F3EAC7 F2E5BC EEE0B7 EBDBB2 F3EAC7',
    ('medium','light'): 'F2E5BC FBF1C7 F4E8BE F2E5BC EEE0B7 E5D5AD DDCCAB F2E5BC',
    ('soft','light'): 'EBDBB2 F2E5BC EDDEB5 EBDBB2 E6D5AE DAC9A5 D5C4A1 EBDBB2',
}
# Upstream visual selection backgrounds: red, green, blue, purple, yellow (only the first four are needed).
MATERIAL_VISUAL = {
    ('hard','dark'): '442E2D 333E34 2E3B3B 3C333B 473C29',
    ('medium','dark'): '4C3432 3B4439 374141 443840 4F422E',
    ('soft','dark'): '543937 424A3E 404946 4B3E45 574833',
    ('hard','light'): 'F0DDC3 DDE5C2 D9E1CC EEE2D1 F9EABF',
    ('medium','light'): 'F1D9B5 DEE2B6 DADEC0 EFDEC3 FAE7B3',
    ('soft','light'): 'EFD2B3 D7D9AE D3D5B8 E8D4BA F3DEAA',
}
MIT = '''Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.'''
NOTICES = {
    'original': 'Palette adapted from morhetz/gruvbox (https://github.com/morhetz/gruvbox).\nUpstream README identifies the license as MIT/X11.\nUpstream author: Pavel Pertsev (morhetz). No dated copyright line or\nstandalone LICENSE was found at the pinned revision; no date is inferred.\nMIT/X11 permission and warranty notice (standard MIT form):\n\n' + MIT,
    'material': 'Palette adapted from sainnhe/gruvbox-material (https://github.com/sainnhe/gruvbox-material).\nMIT License\n\nCopyright (c) 2020 sainnhe\n\n' + MIT,
}


def rgb(h):
    return tuple(int(h[i:i+2],16) for i in (0,2,4))


def mix(a,b,t):
    return ''.join(f'{round(x+(y-x)*t):02X}' for x,y in zip(rgb(a),rgb(b)))


def lum(h):
    def lin(x):
        x/=255
        return x/12.92 if x<=0.04045 else ((x+0.055)/1.055)**2.4
    return sum(x*y for x,y in zip((0.2126,0.7152,0.0722),map(lin,rgb(h))))


def contrast(a,b):
    l1,l2=sorted((lum(a),lum(b)),reverse=True)
    return (l1+0.05)/(l2+0.05)


def accessible(h,bgs,target,endpoint):
    # Smallest integral percentage RGB blend toward the specified endpoint.
    for i in range(101):
        v=mix(h,endpoint,i/100)
        if min(contrast(v,bg) for bg in bgs)>=target:
            return v
    # Reject an impossible request rather than silently lowering the threshold.
    raise ValueError((h,bgs,target,endpoint))


def fg_on(bg):
    choices=('141617','1D2021','282828','FBF1C7','F9F5D7','FFFFFF','000000')
    # Prefer the warmest usable choices, with extra margin when possible.
    for c in choices[:-2]:
        if contrast(c,bg)>=5.0:
            return c
    return max(choices,key=lambda c:contrast(c,bg))


def colors(family,mode):
    return dict(zip(NAMES,ANCHORS[family][mode].split()))


def surfaces(family,level,mode):
    dark=mode=='dark'
    if family=='original':
        if dark:
            dim,base,low,container,high,highest='1D2021','282828','32302F','3C3836',mix('3C3836','504945',.5),'504945'
            lowest,bright=dim,highest
            fg,variant='EBDBB2','D5C4A1'
        else:
            lowest,base,low,container,high,highest='F9F5D7','FBF1C7','F2E5BC','EBDBB2',mix('EBDBB2','D5C4A1',.5),'D5C4A1'
            dim,bright=highest,lowest
            fg,variant='3C3836','504945'
    else:
        bdim,base,b1,b2,b3,b4,b5,st=MATERIAL_BG[level,mode].split()
        if dark:
            dim,lowest,low,container,high,highest,bright=bdim,bdim,b1,st,b3,b5,b5
            fg,variant='D4BE98','DDC7A1'
            # Keep the canonical text colors; cap the brightest raised surface
            # to the nearest readable derivative of the upstream bg5.
            highest=bright={'hard':'504945','medium':'514A45','soft':'524B46'}[level]
        else:
            dim,lowest,low,container,high,highest,bright=b5,base,b1,b2,b3,b4,base
            fg,variant='654735','4F3829'
    return dict(surface=base,onSurface=fg,surfaceDim=dim,surfaceBright=bright,
                surfaceContainerLowest=lowest,surfaceContainerLow=low,
                surfaceContainer=container,surfaceContainerHigh=high,
                surfaceContainerHighest=highest,onSurfaceVariant=variant)


def levels(family):
    return ('medium',) if family=='original' else ('hard','medium','soft')


def containers(family,level,mode,hue):
    if family=='material' and hue!='orange':
        return dict(zip(('red','green','blue','purple','yellow'),MATERIAL_VISUAL[level,mode].split()))[hue]
    return mix(surfaces(family,level,mode)['surface'],colors(family,mode)[hue],.20 if mode=='dark' else .17)


def choose_tone(anchor,mode,predicate):
    endpoint='FFFFFF' if mode=='dark' else '000000'
    for i in range(101):
        v=mix(anchor,endpoint,i/100)
        if predicate(v):return v
    raise ValueError(('no accessible tone',anchor,mode))


def accent_text(family,mode,hue):
    # Shared per brightness across contrast levels. Include actual widget-local
    # text uses and native ink rather than only the ColorScheme role pair.
    raw=[]; ink=[]
    for level in levels(family):
        s=surfaces(family,level,mode)
        raw += [v for k,v in s.items() if k.startswith('surface')]
        if hue in ('green','blue','red'):
            raw += [containers(family,level,mode,'orange')]
            ink += [(s['surfaceContainerLow'],.16),(s['surface'],.08),(s['surfaceContainerLow'],.14)]
            ink += [(containers(family,level,mode,h),.16) for h in ('green','blue')]
    if hue=='aqua':
        # TextButton's native ink uses primary, not the literal Aqua text.
        raw += [mix(surfaces(family,l,mode)[role],accent_text(family,mode,a),26/255)
                for l in levels(family) for a in ('green','blue')
                for role in ('surfaceContainerLow','surfaceContainer')]
    return choose_tone(colors(family,mode)[hue],mode,lambda v:
        min(contrast(v,b) for b in raw)>=4.9 and
        all(contrast(v,mix(b,v,a))>=4.75 for b,a in ink))


def container_foreground(anchor,bg,mode):
    # Flutter tonal buttons use the on-container color as ink. Allow margin.
    return choose_tone(anchor,mode,lambda v: contrast(v,bg)>=5 and contrast(v,mix(bg,v,26/255))>=4.65)


def fill_foreground(bg):
    choices=('141617','1D2021','282828','FBF1C7','F9F5D7','FFFFFF','000000')
    for c in choices:
        if contrast(c,bg)>=5 and contrast(c,mix(bg,c,26/255))>=4.65:return c
    return max(choices,key=lambda c:contrast(c,mix(bg,c,26/255)))


def seed_color(family,accent):
    # A single seed is used in both modes. Maximize worst-case contrast of
    # the directly painted seed on cards, selected file rows and disk tracks.
    bgs=[]
    for level in levels(family):
        for mode in ('dark','light'):
            s=surfaces(family,level,mode);card=s['surfaceContainerLow']
            bgs.extend([card,s['surface'],mix(card,containers(family,level,mode,'orange'),.55),mix(card,'7D7D7D',37/255)])
    candidates=[mix(colors(family,'dark')[accent],colors(family,'light')[accent],i/200) for i in range(201)]
    return max(candidates,key=lambda v:min(contrast(v,b) for b in bgs))


def palette(family,level,accent,mode):
    s=surfaces(family,level,mode)
    c=colors(family,mode); d=mode=='dark'
    opposite=colors(family,'light' if d else 'dark')
    bg=s['surface']; fg=s['onSurface']
    for role,hue in [('primary',accent),('secondary','orange'),('tertiary','purple'),('error','red')]:
        anchor=c[hue]
        # The app uses error as ordinary text (e.g. port-forward errors).
        # A single corrected red per brightness is shared by all contrasts.
        a=accent_text(family,mode,hue) if role in ('primary','error') else anchor
        container=containers(family,level,mode,hue)
        # Use the actual hue for container text when possible; otherwise make
        # the minimum contrast correction toward the brightness foreground.
        on_container=container_foreground(anchor,container,mode)
        s[role]=a
        cap=role[0].upper()+role[1:]
        s['on'+cap]=fill_foreground(a) if role in ('primary','error') else fg_on(a)
        s[role+'Container']=container
        s['on'+cap+'Container']=on_container
        if role!='error':
            # Fixed roles stay identical in light and dark. Their bright tone
            # derives from the canonical dark accent, not from the seed.
            fixed=mix(colors(family,'dark')[hue],'F9F5D7',.62)
            dim=mix(colors(family,'dark')[hue],'F9F5D7',.28)
            s[role+'Fixed']=fixed
            s[role+'FixedDim']=dim
            s['on'+cap+'Fixed']='141617'
            s['on'+cap+'FixedVariant']=accessible(colors(family,'light')[hue],[fixed,dim],5.0,'141617')
    border_bgs=[bg,s['surfaceContainerLow'],s['surfaceContainer'],s['surfaceContainerHigh']]
    s['outline']=accessible('928374',border_bgs,4.8,'FFFFFF' if d else '000000')
    s['outlineVariant']=MATERIAL_BG[level,mode].split()[6] if family=='material' and d else mix(bg,s['outline'],.39)
    s['shadow']='000000';s['scrim']='000000'
    # Inverse roles contrast against the opposite neutral surface.
    s['inverseSurface']=fg
    s['onInverseSurface']=bg
    s['inversePrimary']=accessible(opposite[accent],[fg],5.0,'141617' if d else 'FBF1C7')
    s['surfaceTint']=0
    return s


def component_tables(family,accent):
    # Shared structural styling. State-specific literal hues are only used
    # where the ColorScheme has no corresponding semantic color role.
    t={
      'card':dict(backgroundColor='surfaceContainerLow',radius=12,borderColor='outlineVariant',borderWidth=1,elevation=0,surfaceTintColor=0),
      'tile':dict(selectedTileColor='primaryContainer',selectedColor='onPrimaryContainer',iconColor='onSurfaceVariant',radius=8),
      # Do not override shared Filled/Tonal/Elevated backgrounds, foregrounds,
      # or state ink. Flutter retains its semantic pairs and state defaults.
      'button':dict(radius=10,elevation=0,surfaceTintColor=0),
      'textButton':dict(radius=8),
      'textButton.focused':dict(borderColor='primary',borderWidth=2),
      'outlinedButton':dict(radius=10,borderColor='outline',borderWidth=1),
      'outlinedButton.focused':dict(borderColor='primary',borderWidth=2),
      'iconButton':dict(radius=8),
      'iconButton.focused':dict(borderColor='primary',borderWidth=2),
      'input':dict(filled=True,fillColor='surfaceContainerLow',radius=8,borderColor='outline',borderWidth=1,focusedBorderColor='primary',errorBorderColor='error',disabledBorderColor='outlineVariant'),
      'search':dict(backgroundColor='surfaceContainerLow',radius=10,borderColor='outline',borderWidth=1,textColor='onSurface',hintColor='onSurfaceVariant'),
      'appBar':dict(backgroundColor='surface',foregroundColor='onSurface',titleColor='onSurface',elevation=0,surfaceTintColor=0),
      'navigation':dict(backgroundColor='surfaceContainerLow',indicatorColor='primaryContainer',indicatorRadius=10,selectedIconColor='onPrimaryContainer',unselectedIconColor='onSurfaceVariant',unselectedLabelColor='onSurfaceVariant',elevation=0),
      'segmented':dict(backgroundColor='surfaceContainer',selectedColor='primaryContainer',textColor='onSurfaceVariant',selectedTextColor='onPrimaryContainer',radius=8,borderColor='outline',borderWidth=1),
      'sidebar':dict(backgroundColor='surfaceContainerLow',selectedColor='primaryContainer',textColor='onSurface',selectedTextColor='onPrimaryContainer',iconColor='onSurfaceVariant',radius=8),
      'dialog':dict(backgroundColor='surfaceContainer',radius=16,borderColor='outlineVariant',borderWidth=1,elevation=0,surfaceTintColor=0),
      'sheet':dict(backgroundColor='surfaceContainer',radius=16,elevation=0,surfaceTintColor=0,dragHandleColor='outline'),
      'menu':dict(backgroundColor='surfaceContainerHigh',radius=8,borderColor='outlineVariant',borderWidth=1,elevation=0,surfaceTintColor=0,textColor='onSurface'),
      'tooltip':dict(radius=6),
      'toast':dict(backgroundColor='inverseSurface',textColor='onInverseSurface',radius=10,elevation=0),
      # Native switch retains state-dependent colors, including disabled states.
      'slider':dict(activeTrackColor='primary',inactiveTrackColor='primaryContainer',thumbColor='primary'),
      'progress':dict(color='primary',trackColor='primaryContainer'),
      'badge':dict(backgroundColor='tertiary',textColor='onTertiary'),
      'chip':dict(backgroundColor='surfaceContainerLow',selectedColor='secondaryContainer',textColor='onSurface',radius=8,borderColor='outlineVariant',borderWidth=1),
      'divider':dict(color='outlineVariant',thickness=1),
      'scrollbar':dict(thumbColor='outline',trackColor='surfaceContainerLow',radius=4),
    }
    other='blue' if accent=='green' else 'green'
    for mode in ('dark','light'):
        c=colors(family,mode)
        t[f'{mode}.textButton']=dict(foregroundColor=argb(accent_text(family,mode,'aqua')))
        t[f'{mode}.textButton.disabled']=dict(foregroundColor=int('61'+surfaces(family,'medium',mode)['onSurface'],16))
        t[f'{mode}.iconButton.disabled']=dict(foregroundColor=int('61'+surfaces(family,'medium',mode)['onSurface'],16))
        # The complementary default does not replace the selected semantic pair.
        t[f'{mode}.iconButton.selected']=dict(foregroundColor='onPrimaryContainer',backgroundColor='primaryContainer')
        t[f'{mode}.iconButton.disabled']['backgroundColor']=0
        chip_bgs=[]
        for level in levels(family):
            chip_bgs.extend((surfaces(family,level,mode)['surfaceContainerLow'],containers(family,level,mode,'orange')))
        chip_ink='FFFFFF' if mode=='dark' else '000000'
        chip_fg=choose_tone(surfaces(family,'medium',mode)['onSurface'],mode,lambda v:
            all(contrast(v,mix(b,chip_ink,31/255))>=4.75 for b in chip_bgs))
        t[f'{mode}.chip']=dict(textColor=argb(chip_fg))
        # Preserve the exact canonical red as a non-text error border.
        t[f'{mode}.input']=dict(errorBorderColor=argb(c['red']))
        t[f'{mode}.iconButton']=dict(foregroundColor=argb(accent_text(family,mode,other)))
        t[f'{mode}.search']=dict(iconColor=argb(accent_text(family,mode,other)))
        t[f'{mode}.appBar']=dict(iconColor=argb(accent_text(family,mode,accent)))
        t[f'{mode}.navigation']=dict(selectedLabelColor=argb(accent_text(family,mode,accent)))
        t[f'{mode}.sidebar']=dict(selectedIconColor='onPrimaryContainer')
        # Canonical accent is safe for these non-text consumers. Keep its
        # identity visible rather than forcing all controls to the text tone.
        t[f'{mode}.progress']=dict(color=argb(c[accent]))
        t[f'{mode}.slider']=dict(activeTrackColor=argb(c[accent]),thumbColor=argb(c[accent]))
        t[f'{mode}.tooltip']=dict(backgroundColor=argb(c['yellow']),textColor=argb(fg_on(c['yellow'])))
    return t


def argb(h):
    return int('FF'+h,16) if isinstance(h,str) else h


def literal(value):
    if isinstance(value,bool):return str(value).lower()
    if isinstance(value,str):return json.dumps(value,ensure_ascii=False)
    if isinstance(value,int) and (value>255 or value==0):
        # Zero is valid for both numeric fields and transparent colors.
        return f'0x{value:08X}' if value>255 else '0'
    return str(value)


def table(path,fields):
    return '\n['+path+']\n'+''.join(f'{k} = {"0x00000000" if type(v) is int and v == 0 and k.endswith("Color") else literal(v)}\n' for k,v in fields.items())


def pal_table(path,p):
    return '\n['+path+']\n'+''.join(f'{k} = 0x{argb(v):08X}\n' for k,v in p.items())


def build(family):
    material=family=='material'
    tid='milesclem.gruvbox'+('-material' if material else '')
    name='Gruvbox Material' if material else 'Gruvbox'
    variants=[(f'{level}_{accent}',f'{level.title()} {accent.title()}',level,accent) for level in ('medium','hard','soft') for accent in ('green','blue')] if material else [(accent,accent.title(),'medium',accent) for accent in ('green','blue')]
    base={mode:palette(family,'medium','green',mode) for mode in ('dark','light')}
    components=component_tables(family,'green')
    out=f'#:schema {SCHEMA_URL}\n'+''.join('# '+l+'\n' if l else '#\n' for l in NOTICES[family].splitlines())
    out+='\n# Copyright (c) 2026 milesclem contributors (ServerBox adaptation).\n# The adaptation is licensed under the MIT permission and warranty terms above.\n# Regenerate with tools/generate.py.\n'
    out+=f'id = "{tid}"\nname = "{name}"\nmodes = ["light", "dark"]\n'
    out+=table('schema',dict(min=3,max=4))
    out+=table('colors',dict(mode=0,seed=argb(seed_color(family,'green')),systemColor=False))
    for mode,p in base.items():out+=pal_table('colors.palette.'+mode,p)
    for path,fields in components.items():out+=table('components.'+path,fields)
    for key,label,level,accent in variants:
        prefix='variants.'+key
        out+=table(prefix,dict(name=label))
        if accent!='green':out+=table(prefix+'.colors',dict(seed=argb(seed_color(family,accent))))
        for mode in ('dark','light'):
            p=palette(family,level,accent,mode)
            changed={k:v for k,v in p.items() if v!=base[mode][k]}
            if changed:out+=pal_table(prefix+'.colors.palette.'+mode,changed)
        for path,fields in component_tables(family,accent).items():
            changed={k:v for k,v in fields.items() if v!=components[path].get(k)}
            if changed:out+=table(prefix+'.components.'+path,changed)
    folder=ROOT/'themes'/tid;folder.mkdir(parents=True,exist_ok=True)
    # Same-directory temporary file permits an atomic replacement.
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',newline='\n',dir=folder,prefix='.manifest-',delete=False) as f:
        temp=Path(f.name);f.write(out)
    try:
        os.chmod(temp,0o644);os.replace(temp,folder/'manifest.toml')
    finally:
        temp.unlink(missing_ok=True)


if __name__=='__main__':
    for family in ('original','material'):build(family)

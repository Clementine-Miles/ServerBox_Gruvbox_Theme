#!/usr/bin/env python3
"""Audit the effective themes. Optionally validate with the full upstream schema."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROLES = set('''primary onPrimary primaryContainer onPrimaryContainer primaryFixed primaryFixedDim onPrimaryFixed onPrimaryFixedVariant secondary onSecondary secondaryContainer onSecondaryContainer secondaryFixed secondaryFixedDim onSecondaryFixed onSecondaryFixedVariant tertiary onTertiary tertiaryContainer onTertiaryContainer tertiaryFixed tertiaryFixedDim onTertiaryFixed onTertiaryFixedVariant error onError errorContainer onErrorContainer surface onSurface surfaceDim surfaceBright surfaceContainerLowest surfaceContainerLow surfaceContainer surfaceContainerHigh surfaceContainerHighest onSurfaceVariant outline outlineVariant shadow scrim inverseSurface onInverseSurface inversePrimary surfaceTint'''.split())
# Validation-only projection of the pinned schema for the deliberately narrow
# feature set of these two packages. The full official JSON Schema is checked
# separately when --schema is passed. Do not mistake this for the installer.
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
BG_ROLES = ('surface','surfaceDim','surfaceBright','surfaceContainerLowest','surfaceContainerLow','surfaceContainer','surfaceContainerHigh','surfaceContainerHighest')


def check(c,msg):
    if not c: raise ValueError(msg)


def rgba(v):return type(v) is int and 0<=v<=0xFFFFFFFF


def hexrgb(v):return f'{v&0xFFFFFF:06X}'


def valid_field(kind,value):
    if kind=='color':return rgba(value) or (isinstance(value,str) and value in ROLES)
    if kind=='flag':return type(value) is bool
    if kind=='inset':return isinstance(value,list) and len(value)==4 and all(type(x) in (int,float) and 0<=x<=64 for x in value)
    return type(value) in (int,float) and 0<=value<=BOUNDS[kind]


def check_components(table,path='components',allow_brightness=True):
    check(isinstance(table,dict),path)
    for key,values in table.items():
        if allow_brightness and key in ('dark','light'):
            check_components(values,path+'.'+key,False);continue
        check(key in FIELDS and isinstance(values,dict),path+'.'+key)
        for field,value in values.items():
            if field in STATES and key in STATEFUL:
                check(isinstance(value,dict),path+'.'+key+'.'+field)
                for k,v in value.items():check(k in FIELDS[key] and valid_field(FIELDS[key][k],v),path+'.'+key+'.'+field+'.'+k)
            else:check(field in FIELDS[key] and valid_field(FIELDS[key][field],value),path+'.'+key+'.'+field)


def check_colors(c):
    check(set(c)<= {'mode','seed','systemColor','palette'},'unknown colors field')
    if 'mode' in c:check(type(c['mode']) is int and 0<=c['mode']<=2,'mode')
    if 'seed' in c:check(rgba(c['seed']),'seed')
    if 'systemColor' in c:check(type(c['systemColor']) is bool,'systemColor')
    check(set(c.get('palette',{}))<= {'dark','light'},'unknown brightness')
    for p in c.get('palette',{}).values():check(set(p)<=ROLES and all(rgba(v) for v in p.values()),'palette field/value')


def merge(a,b):
    result=copy.deepcopy(a)
    for k,v in b.items():result[k]=merge(result[k],v) if isinstance(v,dict) and isinstance(result.get(k),dict) else copy.deepcopy(v)
    return result


def resolved_components(c,mode):return merge({k:v for k,v in c.items() if k not in ('light','dark')},c.get(mode,{}))


# Independent oracle: no generator import. Exact arithmetic after sRGB source-over.
IDS = {'milesclem.gruvbox': ['green','blue'], 'milesclem.gruvbox-material': [f'{l}_{a}' for l in ('medium','hard','soft') for a in ('green','blue')]}
BASE = {'medium': {'dark':0xFF282828,'light':0xFFFBF1C7}, 'hard':{'dark':0xFF1D2021,'light':0xFFF9F5D7},'soft':{'dark':0xFF32302F,'light':0xFFF2E5BC}}
CANONICAL = {
    ('original','dark'):'FB4934 FE8019 FABD2F B8BB26 8EC07C 83A598 D3869B',
    ('original','light'):'9D0006 AF3A03 B57614 79740E 427B58 076678 8F3F71',
    ('material','dark'):'EA6962 E78A4E D8A657 A9B665 89B482 7DAEA3 D3869B',
    ('material','light'):'C14A4A C35E0A B47109 6C782E 4C7A5D 45707A 945E80',
}


def read(path):return tomllib.loads(path.read_text(encoding='utf-8'))

def channels(n):return tuple((n>>i&255)/255 for i in (16,8,0,24))

def rgba_over(top,bottom):
    a=top[3]+bottom[3]*(1-top[3])
    if not a:return (0.,0.,0.,0.)
    return tuple((x*top[3]+y*bottom[3]*(1-top[3]))/a for x,y in zip(top[:3],bottom[:3]))+(a,)

def luminance(c):return sum(w*(x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4) for w,x in zip((.2126,.7152,.0722),c[:3]))

def ratio(a,b):
    check(b[3]==1,'opaque substrate required')
    x,y=sorted((luminance(rgba_over(a,b)),luminance(b)))
    return (y+.05)/(x+.05)

def paint(n):return '#'+''.join(f'{math.floor(x*255+.5):02X}' for x in n[:3])

def ink(bg,fg,opacity):return rgba_over((*fg[:3],opacity),bg)

def metadata(require_versions=False):
    repo=read(ROOT/'repo.toml');check(type(repo.get('schema')) is int and repo['schema']==1 and isinstance(repo.get('name'),str) and repo['name'].strip(),'repo metadata')
    themes=ROOT/'themes'
    check({p.stem for p in themes.glob('*.toml')}==set(IDS),'exact listing IDs')
    check({p.name for p in themes.iterdir() if p.is_dir()}==set(IDS),'exact package IDs')
    from urllib.parse import urlparse
    for tid in IDS:
        m=read(themes/tid/'manifest.toml');v=read(themes/(tid+'.toml'))
        check(v.get('id')==tid and v.get('name')==m.get('name'),'listing identity')
        check(v.get('license')=='MIT' and isinstance(v.get('homepage'),str) and urlparse(v['homepage']).scheme=='https' and bool(urlparse(v['homepage']).netloc),'license/homepage')
        d=v.get('description');check(isinstance(d,dict) and {'en','zh','zh-TW'}<=d.keys() and all(isinstance(x,str) and x.strip() for x in d.values()),'description')
        versions=v.get('version',[]);check(isinstance(versions,list),'version array')
        check(not require_versions or bool(versions),f'{tid}: no published version')
        seen=set()
        for x in versions:
            check(isinstance(x,dict),'version table')
            ver=x.get('version');check(isinstance(ver,str) and re.fullmatch(r'\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?',ver) and ver not in seen,'unique version');seen.add(ver)
            check(type(x.get('schema_min')) is int and type(x.get('schema_max')) is int and 1<=x['schema_min']<=x['schema_max'] and x['schema_min']<=4 and x['schema_max']>=3,'version schema')
            check(isinstance(x.get('sha256'),str) and re.fullmatch('[0-9a-f]{64}',x['sha256']) and type(x.get('size')) is int and 0<x['size']<=16*1024*1024,'version digest/size')
            check('url' in x and 'path' not in x and isinstance(x['url'],str) and urlparse(x['url']).scheme=='https' and bool(urlparse(x['url']).netloc),'version URL')
    return all(read(themes/(tid+'.toml')).get('version') for tid in IDS)


def measure(rows,identity,p,c,seed,mode):
    def col(v):return channels(p[v] if isinstance(v,str) else v)
    def add(context,fg,bg,target=4.5,*,layer=None,opacity=0,kind='gate',substrate=None):
        a=col(fg);b=col(bg)
        if b[3]<1:
            check(substrate is not None,'missing substrate');b=rgba_over(b,col(substrate))
        if layer is not None:b=ink(b,col(layer),opacity)
        r=ratio(a,b)
        rows.append(dict(identity,scope=kind,context=context,foreground=paint(rgba_over(a,b)),background=paint(b),ratio=round(r,8),target=target,status='PASS' if r>=target else 'FAIL'))
    for bg in BG_ROLES:
        for fg in ('onSurface','onSurfaceVariant','primary','error'):
            add(f'{fg} on {bg}',fg,bg)
    for name in ('primary','secondary','tertiary','error'):
        on='on'+name.title()
        for suffix in ('','Container'):add(on+suffix,on+suffix,name+suffix)
        if name!='error':
            for bg in ('Fixed','FixedDim'):
                for fg in ('Fixed','FixedVariant'):add(on+fg+' on '+name+bg,on+fg,name+bg)
    add('inverse text','onInverseSurface','inverseSurface');add('inverse action','inversePrimary','inverseSurface')
    # Actual source consumers from the independent audit of the pinned revisions.
    low='surfaceContainerLow';sheet='surfaceContainer';pc='primaryContainer';sc='secondaryContainer'
    for bg in (low,sheet,sc):add('raw primary text','primary',bg)
    for bg,opacity,context in [('surface',.08,'Workspace target'),(low,.14,'Monitor update tag'),(low,.16,'Monitor unselected count'),(pc,.16,'Monitor selected count')]:
        add(context,'primary',bg,layer='primary',opacity=opacity)
    for bg in (low,pc):add('Monitor alert count','error',bg,layer='error',opacity=.16)
    add('Monitor Desk helper text','outline',low)
    add('navigation label',c['navigation']['selectedLabelColor'],low)
    add('rail selected label',c['navigation']['selectedLabelColor'],pc)
    add('navigation icon','onPrimaryContainer',pc,3)
    add('tooltip',c['tooltip']['textColor'],c['tooltip']['backgroundColor'])
    add('badge',c['badge']['textColor'],c['badge']['backgroundColor'])
    add('input focus text','primary',low);add('input error border',c['input']['errorBorderColor'],low,3)
    add('search outline','outline',low,3);add('search icon',c['search']['iconColor'],low,3)
    add('progress fill',c['progress']['color'],c['progress']['trackColor'],3)
    add('slider active',c['slider']['activeTrackColor'],c['slider']['inactiveTrackColor'],3)
    add('slider thumb',c['slider']['thumbColor'],low,3)
    for fg,bg in [('onPrimary','primary'),('onSecondaryContainer',sc),('primary',low)]:
        for state,alpha in [('rest',0),('hover',20/255),('focus',26/255),('press',26/255),('hover+focus',20/255),('press+focus',26/255)]:
            add(f'native Filled/Tonal/Elevated {fg} {state}',fg,bg,layer=fg,opacity=alpha)
    # Transparent outlined fill: local destructive foreground is preserved.
    for bg in ('surface',low,sheet):
        for state,alpha in [('rest',0),('hover',20/255),('focus',26/255),('press',26/255),('hover+focus',20/255),('press+focus',26/255)]:
            add(f'outlined {state}','primary',bg,layer='primary',opacity=alpha)
            add(f'Services Stop {state}','error',bg,layer='error',opacity=alpha)
            add(f'outlined focus border {state}','primary',bg,3,layer='primary',opacity=alpha)
            add(f'Aqua action {state}',c['textButton']['foregroundColor'],bg,layer='primary',opacity=alpha)
            add(f'complementary icon {state}',c['iconButton']['foregroundColor'],bg,3,layer='onSurfaceVariant',opacity=alpha)
    for bg in (low,sc):
        for state,alpha in [('rest',0),('hover',10/255),('focus/press',31/255)]:
            add(f'chip {state}',c['chip']['textColor'],bg,layer=0xFFFFFFFF if mode=='dark' else 0xFF000000,opacity=alpha)
    # These uses are app-owned, not guaranteed correctable in a manifest.
    for bg in (low,'surface'):
        add('legacy direct seed border',seed,bg,3,kind='upstream')
    add('legacy selected row seed',seed,low,3,layer=sc,opacity=.55,kind='upstream')
    add('legacy disk track seed',seed,low,3,layer=0xFF7D7D7D,opacity=37/255,kind='upstream')
    for bg in (low,sheet):
        for name,number in [('red',0xFFF44336),('green',0xFF4CAF50),('grey',0xFF757575 if bg==low else 0xFF9E9E9E)]:
            add('hardcoded statistics '+name,number,bg,kind='upstream')
    for bg in (low,'surfaceContainer',sc):add('selection fill only',pc,bg,3,kind='conditional')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--schema',type=Path);ap.add_argument('--json',type=Path);ap.add_argument('--packages',type=Path);ap.add_argument('--require-versions',action='store_true');args=ap.parse_args()
    schema=None
    if args.schema:
        raw=args.schema.read_bytes()
        check(hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()=='174e1d7bff0b825ddd00d79fe95f7abfc8f5685e','schema must match pinned upstream Git blob')
        schema=json.loads(raw)
    check(abs(ratio(channels(0xFFFFFFFF),channels(0xFF000000))-21)<1e-10,'WCAG oracle')
    check(paint(rgba_over(channels(0x80FF0000),channels(0xFF0000FF)))=='#80007F','alpha oracle')
    has_versions=metadata(args.require_versions);rows=[];packages=[];appearances=0
    for tid,keys in IDS.items():
        path=ROOT/'themes'/tid/'manifest.toml';m=read(path)
        check(not path.parent.is_symlink() and not path.is_symlink() and path.stat().st_size<=64*1024 and set(x.name for x in path.parent.iterdir())=={'manifest.toml'},'package contents')
        check(set(m)=={'id','name','modes','schema','colors','components','variants'} and m['name']==('Gruvbox Material' if tid.endswith('-material') else 'Gruvbox') and m['id']==tid and m['modes']==['light','dark'] and m['schema']=={'min':3,'max':4},'package identity/schema')
        check(list(m['variants'])==keys,'variant order');check_colors(m['colors']);check_components(m['components'])
        if schema:
            from jsonschema import validators
            validators.validator_for(schema)(schema).validate(m)
        base={k:v for k,v in m.items() if k!='variants'};resolved={}
        for key,v in m['variants'].items():
            check(v['name']==key.replace('_',' ').title() and set(v)<= {'name','colors','components'},'variant fields')
            check_colors(v.get('colors',{}));check_components(v.get('components',{}))
            effective=merge(base,{k:x for k,x in v.items() if k!='name'})
            col=effective['colors'];check(col['mode']==0 and col['systemColor'] is False,'mode')
            level,accent=key.split('_') if '_' in key else ('medium',key);family='material' if tid.endswith('-material') else 'original'
            for mode in ('dark','light'):
                p=col['palette'][mode];c=resolved_components(effective['components'],mode)
                anchors=dict(zip('red orange yellow green aqua blue purple'.split(),[int('FF'+h,16) for h in CANONICAL[family,mode].split()]))
                check(set(p)==ROLES and p['surfaceTint']==0 and all(x>>24==255 for k,x in p.items() if k!='surfaceTint'),'explicit roles')
                check(p['surface']==BASE[level][mode] and p['secondary']==anchors['orange'] and p['tertiary']==anchors['purple'],'canonical colors')
                check(c['progress']['color']==anchors[accent] and c['slider']['thumbColor']==anchors[accent] and c['tooltip']['backgroundColor']==anchors['yellow'] and c['input']['errorBorderColor']==anchors['red'],'canonical visible accents')
                check(c['badge']['backgroundColor']=='tertiary' and c['chip']['selectedColor']=='secondaryContainer','supporting accents')
                check(not {'backgroundColor','foregroundColor','overlayColor'} & c['button'].keys() and not {'backgroundColor','foregroundColor','overlayColor','hovered','pressed'} & c['outlinedButton'].keys(),'native button semantics')
                for item in ('card','button','appBar','dialog','sheet','menu'):check(c[item]['surfaceTintColor']==0,'component tint')
                ladder=[luminance(channels(p[r])) for r in ('surfaceContainerLowest','surfaceContainerLow','surfaceContainer','surfaceContainerHigh','surfaceContainerHighest')]
                check(ladder==sorted(ladder,reverse=mode=='light'),'surface ladder')
                resolved[key,mode]=p;appearances+=1
                measure(rows,{'id':tid,'variant':key,'mode':mode},p,c,col['seed'],mode)
            check(all(resolved[key,'light'][r]==resolved[key,'dark'][r] for r in ROLES if 'Fixed' in r),'fixed roles invariant')
        for level in ('medium','hard','soft') if family=='material' else ('medium',):
            for mode in ('dark','light'):
                g,b=(level+'_green',level+'_blue') if family=='material' else ('green','blue');pg,pb=resolved[g,mode],resolved[b,mode]
                check(all(pg[r]==pb[r] for r in ROLES if 'Primary' not in r and not r.startswith('primary')),'accent changes non-primary roles')
        if args.packages:
            f=args.packages/(tid+'-preview.fsbt')
            with zipfile.ZipFile(f) as z:check(z.namelist()==['manifest.toml'] and z.testzip() is None and z.read('manifest.toml')==path.read_bytes(),'package bytes')
            packages.append({'name':f.name,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'size':f.stat().st_size})
    check(appearances==16,'appearance count')
    if args.packages:check({p.name for p in args.packages.glob('*.fsbt')}=={tid+'-preview.fsbt' for tid in IDS},'exact preview set')
    counts={k:{s:sum(r['scope']==k and r['status']==s for r in rows) for s in ('PASS','FAIL')} for k in ('gate','upstream','conditional')}
    result={'appearances':appearances,'counts':counts,'full_official_schema_checked':schema is not None,'listing_versions_present':has_versions,'packages':packages,'rows':rows}
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
    for row in rows:
        if row['scope']=='gate' and row['status']=='FAIL':print(row)
    if args.json:args.json.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return int(bool(counts['gate']['FAIL']))

if __name__=='__main__':raise SystemExit(main())

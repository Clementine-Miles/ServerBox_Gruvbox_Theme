#!/usr/bin/env python3
"""Run the pinned official ServerBox tools; never publishes or pushes."""
from pathlib import Path
import argparse
import hashlib
import subprocess
import shutil
import sys
import tempfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
REV='fa7941a0b3d4dda154cbf85b007dc6348812e679'
BASE=f'https://raw.githubusercontent.com/lollipopkit/flutter_server_box/{REV}/'
SCRIPTS='.claude/skills/serverbox-theme/scripts/'
PINNED={
    'docs/schemas/fsbt-manifest.schema.json':'174e1d7bff0b825ddd00d79fe95f7abfc8f5685e',
    SCRIPTS+'validate.py':'b42ccb538b0413b715c65736469d5e5eb52ddce3',
    SCRIPTS+'pack.py':'506aae37fb31a72eea2e7f274ae184c54987f352',
    SCRIPTS+'publish.py':'90304933004aff0ec5562e72cae00926d21f77fa',
}


def blob_sha(data):return hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()


def retrieve(target,checkout):
    for rel,expected in PINNED.items():
        if checkout:
            data=(checkout/rel).read_bytes()
        else:
            with urllib.request.urlopen(BASE+rel,timeout=30) as response:data=response.read()
        if blob_sha(data)!=expected:raise RuntimeError(f'Unexpected upstream bytes: {rel}')
        p=target/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)


def run(*args,cwd=ROOT):
    print('+',' '.join(map(str,args)),flush=True)
    subprocess.run([str(a) for a in args],cwd=cwd,check=True)


def verify_generator():
    files=sorted((ROOT/'themes').glob('*/manifest.toml'))
    before={p:p.read_bytes() for p in files}
    run(sys.executable,ROOT/'tools/generate.py')
    if any(p.read_bytes()!=data for p,data in before.items()):
        raise RuntimeError('Generated manifests changed. Review and commit them before retrying.')



def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--serverbox',type=Path,help='local ServerBox checkout of pinned commit; defaults to fetching pinned files')
    ap.add_argument('--preview-dir',type=Path,default=ROOT.parent/'previews')
    ap.add_argument('--skip-dry-run',action='store_true',help='validate and package only; use before a GitHub origin exists')
    a=ap.parse_args();out=a.preview_dir.resolve()
    if out==ROOT or ROOT in out.parents:ap.error('keep the preview directory outside the repository')
    if out.exists() and any(out.iterdir()):ap.error('use an empty or new preview directory')
    # Do not rely on validate.py's exit code alone: it can skip the schema.
    checker=shutil.which('check-jsonschema')
    if not checker:ap.error('install check-jsonschema on PATH (e.g. uv tool install check-jsonschema); full schema validation is mandatory')
    try:import jsonschema  # independent local cross-check, see README
    except ImportError:ap.error('install jsonschema in the Python environment running this script')
    verify_generator()
    out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='serverbox-theme-') as d:
        upstream=Path(d);retrieve(upstream,a.serverbox)
        scripts=upstream/SCRIPTS;schema=upstream/'docs/schemas/fsbt-manifest.schema.json'
        run(sys.executable,ROOT/'tools/audit.py','--schema',schema)
        for folder in sorted((ROOT/'themes').glob('*/')):
            run(checker,'--schemafile',schema,folder/'manifest.toml',cwd=upstream)
            run(sys.executable,scripts/'validate.py',folder,'--schema',schema,cwd=upstream)
            target=out/(folder.name+'-preview.fsbt')
            run(sys.executable,scripts/'pack.py',folder,'-o',target,cwd=upstream)
            repeat=upstream/target.name
            run(sys.executable,scripts/'pack.py',folder,'-o',repeat,cwd=upstream)
            if repeat.read_bytes()!=target.read_bytes():raise RuntimeError('Packaging was not reproducible')
        run(sys.executable,ROOT/'tools/audit.py','--schema',schema,'--packages',out,'--json',out/'audit.json')
        if not a.skip_dry_run:
            # Run from the isolated staged checkout: schema discovery uses
            # the pinned schema there rather than a working-directory ancestor.
            run(sys.executable,scripts/'publish.py','--root',ROOT,'--dry-run',cwd=upstream)


if __name__=='__main__':main()

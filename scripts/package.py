"""Create a submission ZIP without virtual environments, caches, or credentials."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT=Path(__file__).resolve().parents[1]
EXCLUDE={'.venv','.git','__pycache__','.pytest_cache'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT.parent/'research-reliability-bench.zip')
    args=p.parse_args()
    files=[x for x in ROOT.rglob('*') if x.is_file() and not any(a in EXCLUDE for a in x.relative_to(ROOT).parts)
           and x.name!='.env' and x.suffix!='.pyc']
    for path in files:
        payload=path.read_bytes()
        if re.search(rb'(?:sk-proj-|dtn_)[A-Za-z0-9_-]{20,}',payload):
            raise SystemExit(f'Refusing to package a credential-like value in {path.relative_to(ROOT)}')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in sorted(files): z.write(path,arcname=str(Path(ROOT.name)/path.relative_to(ROOT)))
    digest=hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(json.dumps({'file':str(args.output),'files':len(files),'bytes':args.output.stat().st_size,'sha256':digest}))


if __name__=='__main__':main()

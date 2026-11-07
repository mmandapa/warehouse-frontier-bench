"""Prepare build contexts from the checksummed official UCI archive; no private data enters the agent context."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import zipfile
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SOURCE_SHA256 = "c00b803081a5c797cd5e4b83700a9810b38d53d9d84e01917e090e1fdbc81031"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive", type=Path)
    args = p.parse_args()
    payload = args.archive.read_bytes()
    if hashlib.sha256(payload).hexdigest() != SOURCE_SHA256:
        raise SystemExit("Official archive checksum mismatch")
    outer = zipfile.ZipFile(io.BytesIO(payload))
    z = zipfile.ZipFile(io.BytesIO(outer.read("UCI HAR Dataset.zip")))
    task = ROOT / "tasks/unseen-subject-audit"
    workspace = task / "environment/workspace"
    trusted = task / "tests/data"
    (workspace / "data").mkdir(parents=True, exist_ok=True)
    trusted.mkdir(parents=True, exist_ok=True)
    manifest = {"source_url": "https://archive.ics.uci.edu/static/public/240/human+activity+recognition+using+smartphones.zip",
                "source_sha256": SOURCE_SHA256, "license": "CC BY 4.0", "doi": "10.24432/C54S4K", "partitions": {}}
    for split, output in (("train", "dev"), ("test", "private")):
        def read(name):
            return np.loadtxt(io.BytesIO(z.read(f"UCI HAR Dataset/{split}/{name}_{split}.txt")))
        X, y, subjects = read("X"), read("y").astype(int), read("subject").astype(int)
        path = trusted / f"{output}.npz"
        np.savez_compressed(path, X=X, y=y, subjects=subjects)
        manifest["partitions"][output] = {"rows":len(y), "features":X.shape[1], "subjects":np.unique(subjects).tolist(),
                                           "sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
    shutil.copy2(trusted / "dev.npz", workspace / "data/dev.npz")
    for name in ("README.txt", "features_info.txt", "features.txt", "activity_labels.txt"):
        (workspace / "data" / name).write_bytes(z.read(f"UCI HAR Dataset/{name}"))
    for dest in (workspace / "rrbench", task / "tests/rrbench"):
        shutil.copytree(ROOT / "src/rrbench", dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    (workspace / "rrbench/verifier.py").unlink(missing_ok=True)
    # Linux wheel tie-breaking can differ from host wheels. The image build
    # creates this report with the runtime used by the agent and verifier.
    (workspace / "original_report.json").unlink(missing_ok=True)
    (ROOT / "data-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k:v['rows'] for k,v in manifest['partitions'].items()}))


if __name__ == "__main__": main()

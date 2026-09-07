#!/usr/bin/env python3
"""Verify official read-only files against the downloaded CANNJudge template."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def check(root=ROOT, template=None):
    if template:
        files = json.loads(Path(template).read_text())["data"]["files"]
        expected = {f["path"]: hashlib.sha256(f["content"].encode()).hexdigest()
                    for f in files if not f.get("editable", False)}
    else:
        expected = json.loads((ROOT / "tools/official_template_hashes.json").read_text())
    failures = []
    for relative, digest in expected.items():
        path = root / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            failures.append(relative)
    if failures:
        raise RuntimeError("Official read-only files changed or missing: " + ", ".join(failures))
    print(f"PASS: {len(expected)} official read-only files are byte-identical; kernel.asc is editable.")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, help="Optional original API response JSON")
    args = parser.parse_args()
    check(template=args.template)

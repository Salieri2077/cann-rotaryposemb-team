#!/usr/bin/env python3
"""Prepare local submission files; performs no network request or submission."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import zipfile
from check_template import ROOT, check

# Identifiers reported by the judge, plus fprintf observed in our rejected source.
# This conservative raw-source scan also catches occurrences in comments/strings.
# It is a local precheck, not an implementation of the platform's complete rules.
FORBIDDEN_IDENTIFIERS = re.compile(
    rb"\b(?:printf|fprintf|cout|cerr|puts|write|syscall|dlopen|dlsym|asm|freopen)\b"
)

def check_source_identifiers(source: bytes, filename: str = "kernel.asc"):
    violations = []
    for line_number, line in enumerate(source.splitlines(), start=1):
        for match in FORBIDDEN_IDENTIFIERS.finditer(line):
            identifier = match.group().decode("ascii")
            violations.append(f"{filename}:{line_number}: forbidden identifier '{identifier}'")
    if violations:
        raise RuntimeError(
            "Local source precheck found known forbidden identifiers "
            "(this does not cover all platform rules):\n" + "\n".join(violations)
        )

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    check()
    kernel = (ROOT / "kernel.asc").read_bytes()
    if not kernel or b"run_kernel" not in kernel:
        raise RuntimeError("kernel.asc is empty or lacks its required launch function")
    check_source_identifiers(kernel)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "kernel.asc").write_bytes(kernel)
    (output / "kernel_submit.txt").write_bytes(kernel)
    archive = output / "rotaryposemb_submission.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        handle.writestr("kernel.asc", kernel)
    with zipfile.ZipFile(archive) as handle:
        assert handle.namelist() == ["kernel.asc"]
        assert handle.read("kernel.asc") == kernel
    print(json.dumps({"kernel": str(output / "kernel.asc"), "archive": str(archive),
                      "sha256": hashlib.sha256(kernel).hexdigest(),
                      "bytes": len(kernel), "submitted": False}, indent=2))

if __name__ == "__main__":
    main()

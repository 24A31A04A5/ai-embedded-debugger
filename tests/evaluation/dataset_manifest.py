"""Freeze and verify the evaluation datasets (dev and holdout separately).

    python tests/evaluation/dataset_manifest.py --freeze   # after an approved case change
    python tests/evaluation/dataset_manifest.py --verify   # run_eval.py does this automatically

Each case file is hashed with SHA-256 over its bytes with line endings normalised to LF, so a
Windows checkout (CRLF) gives the same hashes. Each split gets a manifest hash: SHA-256 over the
sorted lines "<file name>  <file sha256>\\n" of that split only, so a change to a holdout case
never changes the dev hash and vice versa.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EVAL_DIR = Path(__file__).resolve().parent
CASES_DIR = EVAL_DIR / "cases"
MANIFEST = EVAL_DIR / "DATASET_MANIFEST.json"
SPLITS = ("dev", "holdout")


def file_sha256(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def split_hash(files: dict[str, str]) -> str:
    joined = "".join(f"{name}  {digest}\n" for name, digest in sorted(files.items()))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def compute(cases_dir: Path = CASES_DIR) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {s: {"files": {}} for s in SPLITS}
    for path in sorted(cases_dir.glob("*.json")):
        split = json.loads(path.read_text(encoding="utf-8"))["split"]
        out[split]["files"][path.name] = file_sha256(path)
    for s in SPLITS:
        out[s]["count"] = len(out[s]["files"])
        out[s]["manifest_sha256"] = split_hash(out[s]["files"])
    return out


def freeze(note: str) -> dict[str, Any]:
    manifest = {
        "frozen_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": note,
        "hashing": "sha256 of file bytes with CRLF normalised to LF; split hash = sha256 of sorted '<name>  <sha256>\\n' lines",
        "splits": compute(),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify(cases_dir: Path = CASES_DIR, manifest_path: Path = MANIFEST) -> list[str]:
    """Return a list of problems; empty means both splits match the frozen manifest."""
    if not manifest_path.exists():
        return [f"{manifest_path.name} missing: run dataset_manifest.py --freeze after review"]
    frozen = json.loads(manifest_path.read_text(encoding="utf-8"))["splits"]
    current = compute(cases_dir)
    problems: list[str] = []
    for s in SPLITS:
        f, c = frozen[s]["files"], current[s]["files"]
        for name in sorted(set(f) | set(c)):
            if name not in c:
                problems.append(f"{s}: {name} missing")
            elif name not in f:
                problems.append(f"{s}: {name} not in manifest")
            elif f[name] != c[name]:
                problems.append(f"{s}: {name} changed")
        if not problems and current[s]["manifest_sha256"] != frozen[s]["manifest_sha256"]:
            problems.append(f"{s}: manifest hash mismatch")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--freeze", action="store_true")
    g.add_argument("--verify", action="store_true")
    ap.add_argument("--note", default="")
    args = ap.parse_args()
    if args.freeze:
        m = freeze(args.note)
        for s in SPLITS:
            print(f"{s}: {m['splits'][s]['count']} files, {m['splits'][s]['manifest_sha256']}")
        return 0
    problems = verify()
    if problems:
        print("Dataset does not match DATASET_MANIFEST.json:\n  " + "\n  ".join(problems))
        return 1
    print("Dataset matches DATASET_MANIFEST.json (dev and holdout).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

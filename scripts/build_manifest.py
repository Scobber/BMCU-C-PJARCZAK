#!/usr/bin/env python3
"""
build_manifest.py
Generate manifest.json, manifest.csv, and SHA256SUMS.txt from a staging
directory that contains one sub-directory per firmware environment.

Expected staging layout:
  dist-stage/
    dm_pro_ams_a_010/
      firmware.bin
      metadata.json        (written by the build job; contains env, role, etc.)
    ...

Usage:
  python3 scripts/build_manifest.py \
      --bin-dir  dist-stage \
      --out-dir  dist \
      --git-sha  <SHA> \
      --git-ref  <ref> \
      --pio-version <ver> \
      --py-version  <ver>
"""

import argparse
import csv
import datetime
import hashlib
import json
import os
import sys

# ── Expected matrix ──────────────────────────────────────────────────────────
ROLES = ["ams_a", "ams_b", "ams_c", "ams_d", "solo", "lite"]
LENGTHS = ["010", "020", "025", "030", "035", "040", "045", "050",
           "055", "060", "065", "070", "075", "080", "085", "090"]

# Map role key → human label and AMS number
ROLE_META = {
    "ams_a": {"label": "AMS-A", "ams_num": 0},
    "ams_b": {"label": "AMS-B", "ams_num": 1},
    "ams_c": {"label": "AMS-C", "ams_num": 2},
    "ams_d": {"label": "AMS-D", "ams_num": 3},
    "solo":  {"label": "SOLO",  "ams_num": 0},  # alias of AMS A (no distinct protocol impl)
    "lite":  {"label": "LITE",  "ams_num": 0},  # alias of AMS A (no distinct protocol impl)
}

LENGTH_MM  = {l: int(l) * 10 for l in LENGTHS}   # "010" -> 100 mm
LENGTH_M   = {l: int(l) / 100.0 for l in LENGTHS} # "010" -> 0.10 m


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_env(env: str) -> dict:
    """Parse environment name into role and length parts."""
    # env = dm_pro_{role}_{len}  where role may be ams_a, ams_b, ..., solo, lite
    parts = env.split("_")
    # dm, pro, ..., length (last part)
    length = parts[-1]
    role = "_".join(parts[2:-1])
    return {"role": role, "length": length}


def build_manifest(bin_dir: str, out_dir: str, git_sha: str, git_ref: str,
                   pio_version: str, py_version: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    records = []
    for role in ROLES:
        for length in LENGTHS:
            env = f"dm_pro_{role}_{length}"
            bin_path = os.path.join(bin_dir, env, "firmware.bin")
            renamed  = f"BMCU-DM-PRO-{ROLE_META[role]['label']}-{length}.bin"

            if not os.path.isfile(bin_path):
                print(f"[WARN] Missing: {bin_path}", file=sys.stderr)
                records.append({
                    "environment":    env,
                    "filename":       renamed,
                    "role":           ROLE_META[role]["label"],
                    "ams_num":        ROLE_META[role]["ams_num"],
                    "retract_mm":     LENGTH_MM[length],
                    "retract_m":      LENGTH_M[length],
                    "size_bytes":     None,
                    "sha256":         None,
                    "git_sha":        git_sha,
                    "git_ref":        git_ref,
                    "pio_version":    pio_version,
                    "python_version": py_version,
                    "build_time_utc": timestamp,
                    "build_result":   "MISSING",
                })
                continue

            size   = os.path.getsize(bin_path)
            digest = sha256_file(bin_path)
            records.append({
                "environment":    env,
                "filename":       renamed,
                "role":           ROLE_META[role]["label"],
                "ams_num":        ROLE_META[role]["ams_num"],
                "retract_mm":     LENGTH_MM[length],
                "retract_m":      LENGTH_M[length],
                "size_bytes":     size,
                "sha256":         digest,
                "git_sha":        git_sha,
                "git_ref":        git_ref,
                "pio_version":    pio_version,
                "python_version": py_version,
                "build_time_utc": timestamp,
                "build_result":   "SUCCESS",
            })

    # ── manifest.json ─────────────────────────────────────────────────────
    json_path = os.path.join(out_dir, "manifest.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_utc": timestamp,
            "git_sha":        git_sha,
            "git_ref":        git_ref,
            "pio_version":    pio_version,
            "python_version": py_version,
            "total_builds":   len(records),
            "firmware":       records,
        }, f, indent=2)
    print(f"[OK] manifest.json -> {json_path}")

    # ── manifest.csv ──────────────────────────────────────────────────────
    csv_path = os.path.join(out_dir, "manifest.csv")
    fieldnames = [
        "environment", "filename", "role", "ams_num",
        "retract_mm", "retract_m",
        "size_bytes", "sha256",
        "git_sha", "git_ref", "pio_version", "python_version",
        "build_time_utc", "build_result",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(records)
    print(f"[OK] manifest.csv  -> {csv_path}")

    # ── SHA256SUMS.txt ────────────────────────────────────────────────────
    sums_path = os.path.join(out_dir, "SHA256SUMS.txt")
    with open(sums_path, "w", encoding="utf-8") as f:
        for r in records:
            if r["sha256"]:
                f.write(f"{r['sha256']}  {r['filename']}\n")
    print(f"[OK] SHA256SUMS.txt -> {sums_path}")

    # ── Check for any failures ────────────────────────────────────────────
    failures = [r for r in records if r["build_result"] != "SUCCESS"]
    if failures:
        print(f"[FAIL] {len(failures)} builds did not produce a binary:", file=sys.stderr)
        for r in failures:
            print(f"  - {r['environment']}", file=sys.stderr)
        sys.exit(1)

    print(f"[OK] {len(records)} firmware records written.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build firmware manifest")
    parser.add_argument("--bin-dir",     required=True)
    parser.add_argument("--out-dir",     required=True)
    parser.add_argument("--git-sha",     default="unknown")
    parser.add_argument("--git-ref",     default="unknown")
    parser.add_argument("--pio-version", default="unknown")
    parser.add_argument("--py-version",  default="unknown")
    args = parser.parse_args()

    build_manifest(
        bin_dir=args.bin_dir,
        out_dir=args.out_dir,
        git_sha=args.git_sha,
        git_ref=args.git_ref,
        pio_version=args.pio_version,
        py_version=args.py_version,
    )


if __name__ == "__main__":
    main()

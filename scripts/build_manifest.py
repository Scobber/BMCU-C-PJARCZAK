#!/usr/bin/env python3
"""
build_manifest.py
Generate manifest.json, manifest.csv, and SHA256SUMS.txt from a staging
directory that contains one sub-directory per firmware environment.

Expected staging layout:
  dist-stage/
    dm_pro_ams_a_010/
      firmware.bin
    ...

Usage:
  python3 scripts/build_manifest.py \
      --bin-dir  dist-stage \
      --out-dir  dist \
      --git-sha  <SHA> \
      --git-ref  <ref> \
      --pio-version <ver> \
      --py-version  <ver> \
      [--run-id  <GitHub Actions run ID>]
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

# Map role key → human label, AMS number, and implementation note
ROLE_META = {
    "ams_a": {
        "label":   "AMS-A",
        "ams_num": 0,
        "impl_note": None,  # primary AMS slot A
    },
    "ams_b": {
        "label":   "AMS-B",
        "ams_num": 1,
        "impl_note": None,
    },
    "ams_c": {
        "label":   "AMS-C",
        "ams_num": 2,
        "impl_note": None,
    },
    "ams_d": {
        "label":   "AMS-D",
        "ams_num": 3,
        "impl_note": None,
    },
    "solo": {
        "label":   "SOLO",
        "ams_num": 0,
        "impl_note": (
            "Currently protocol-equivalent to AMS A; "
            "dedicated build flag (BMCU_DM_SOLO) reserved for future differentiation."
        ),
    },
    "lite": {
        "label":   "LITE",
        "ams_num": 0,
        "impl_note": (
            "Currently protocol-equivalent to AMS A; "
            "dedicated build flag (BMCU_DM_LITE) reserved for future differentiation."
        ),
    },
}

LENGTH_MM  = {l: int(l) * 10 for l in LENGTHS}   # "010" -> 100 mm
LENGTH_M   = {l: int(l) / 100.0 for l in LENGTHS} # "010" -> 0.10 m

# Fixed firmware-semantic fields that are the same for every record
FIRMWARE_SEMANTICS = {
    "product":                  "BMCU 370C DM PRO",
    "target_printer":           "Bambu Lab A1",
    "normal_unload_completion": "FRONT_SWITCH_CLEARED",
    "rear_switch_function":     "autoload trigger",
    "front_switch_function":    "normal unload completion",
    "retract_limit_type":       "maximum/fallback distance",
}


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(bin_dir: str, out_dir: str, git_sha: str, git_ref: str,
                   pio_version: str, py_version: str, run_id: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    records = []
    for role in ROLES:
        meta = ROLE_META[role]
        for length in LENGTHS:
            env      = f"dm_pro_{role}_{length}"
            filename = f"BMCU-DM-PRO-{meta['label']}-{length}.bin"
            bin_path = os.path.join(bin_dir, env, "firmware.bin")

            base = {
                "environment":            env,
                "filename":               filename,
                # ── role identity ──
                "role":                   meta["label"],
                "ams_num":                meta["ams_num"],
                "implementation_note":    meta["impl_note"],
                # ── firmware semantics ──
                **FIRMWARE_SEMANTICS,
                # ── retract limit ──
                "retract_limit_mm":       LENGTH_MM[length],
                "retract_limit_m":        LENGTH_M[length],
                # ── reproducibility ──
                "git_sha":                git_sha,
                "git_ref":                git_ref,
                "workflow_run_id":        run_id,
                "pio_version":            pio_version,
                "python_version":         py_version,
                "build_time_utc":         timestamp,
            }

            if not os.path.isfile(bin_path):
                print(f"[WARN] Missing: {bin_path}", file=sys.stderr)
                records.append({
                    **base,
                    "firmware_size_bytes": None,
                    "sha256":              None,
                    "build_result":        "MISSING",
                })
                continue

            size   = os.path.getsize(bin_path)
            digest = sha256_file(bin_path)
            records.append({
                **base,
                "firmware_size_bytes": size,
                "sha256":              digest,
                "build_result":        "SUCCESS",
            })

    # ── manifest.json ─────────────────────────────────────────────────────
    json_path = os.path.join(out_dir, "manifest.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_utc":  timestamp,
            "git_sha":        git_sha,
            "git_ref":        git_ref,
            "workflow_run_id": run_id,
            "pio_version":    pio_version,
            "python_version": py_version,
            "total_builds":   len(records),
            "firmware":       records,
        }, f, indent=2)
    print(f"[OK] manifest.json -> {json_path}")

    # ── manifest.csv ──────────────────────────────────────────────────────
    csv_path = os.path.join(out_dir, "manifest.csv")
    fieldnames = [
        "environment", "filename",
        "role", "ams_num", "implementation_note",
        "product", "target_printer",
        "normal_unload_completion", "rear_switch_function", "front_switch_function",
        "retract_limit_mm", "retract_limit_m", "retract_limit_type",
        "firmware_size_bytes", "sha256",
        "git_sha", "git_ref", "workflow_run_id",
        "pio_version", "python_version",
        "build_time_utc", "build_result",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
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
    parser.add_argument("--run-id",      default="unknown",
                        help="GitHub Actions workflow run ID")
    args = parser.parse_args()

    build_manifest(
        bin_dir=args.bin_dir,
        out_dir=args.out_dir,
        git_sha=args.git_sha,
        git_ref=args.git_ref,
        pio_version=args.pio_version,
        py_version=args.py_version,
        run_id=args.run_id,
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
validate_build_matrix.py
Verify that exactly the 96 expected DM PRO firmware environments are present
in platformio.ini, and (optionally) that exactly 96 firmware.bin files have
been collected in the staging directory produced by the build matrix jobs.

Usage:
  # Check platformio.ini only:
  python3 scripts/validate_build_matrix.py --check-ini

  # Check collected binaries after matrix build:
  python3 scripts/validate_build_matrix.py --check-bins --bin-dir dist-stage
"""

import argparse
import configparser
import os
import sys

# ── Expected matrix ──────────────────────────────────────────────────────────
ROLES = ["ams_a", "ams_b", "ams_c", "ams_d", "solo", "lite"]
LENGTHS = ["010", "020", "025", "030", "035", "040", "045", "050",
           "055", "060", "065", "070", "075", "080", "085", "090"]

EXPECTED_ENVS = [f"dm_pro_{role}_{length}" for role in ROLES for length in LENGTHS]
assert len(EXPECTED_ENVS) == 96, "Matrix must be exactly 96 entries"


def check_ini(ini_path: str) -> bool:
    """Return True if platformio.ini contains exactly the 96 expected envs."""
    cfg = configparser.ConfigParser(strict=False)
    cfg.read(ini_path)

    present = {s[len("env:"):] for s in cfg.sections() if s.startswith("env:")}
    # Remove base env
    present.discard("dm_pro_base")

    missing = [e for e in EXPECTED_ENVS if e not in present]
    extra   = sorted(present - set(EXPECTED_ENVS))

    ok = True
    if missing:
        print(f"[FAIL] {len(missing)} expected environments missing from platformio.ini:")
        for e in missing:
            print(f"  - {e}")
        ok = False
    if extra:
        print(f"[WARN] {len(extra)} unexpected environments in platformio.ini:")
        for e in extra:
            print(f"  - {e}")

    if ok:
        print(f"[OK] platformio.ini contains all {len(EXPECTED_ENVS)} expected environments.")
    return ok


def check_bins(bin_dir: str) -> bool:
    """Return True if bin_dir contains exactly one non-empty .bin per expected env."""
    ok = True
    missing = []
    empty   = []
    found   = 0

    for env in EXPECTED_ENVS:
        path = os.path.join(bin_dir, env, "firmware.bin")
        if not os.path.isfile(path):
            missing.append(env)
        elif os.path.getsize(path) == 0:
            empty.append(env)
        else:
            found += 1

    if missing:
        print(f"[FAIL] {len(missing)} expected firmware.bin files are missing:")
        for e in missing:
            print(f"  - {e}/firmware.bin")
        ok = False
    if empty:
        print(f"[FAIL] {len(empty)} firmware.bin files are zero bytes:")
        for e in empty:
            print(f"  - {e}/firmware.bin")
        ok = False

    # Validate role/length completeness
    by_role = {}
    for env in EXPECTED_ENVS:
        role = "_".join(env.split("_")[2:-1])  # dm_pro_{role}_{len}
        by_role.setdefault(role, []).append(env)

    for role in ROLES:
        envs_for_role = by_role.get(role, [])
        if len(envs_for_role) != len(LENGTHS):
            print(f"[FAIL] Role {role}: expected {len(LENGTHS)} lengths, "
                  f"found {len(envs_for_role)}")
            ok = False

    if ok:
        print(f"[OK] All {found} firmware binaries present and non-empty.")
        print(f"[OK] All 6 roles have exactly 16 lengths.")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate DM PRO build matrix")
    parser.add_argument("--check-ini",  action="store_true",
                        help="Validate platformio.ini environments")
    parser.add_argument("--check-bins", action="store_true",
                        help="Validate collected firmware.bin files")
    parser.add_argument("--ini",     default="platformio.ini",
                        help="Path to platformio.ini (default: platformio.ini)")
    parser.add_argument("--bin-dir", default="dist-stage",
                        help="Directory containing per-env subdirs with firmware.bin")
    args = parser.parse_args()

    if not args.check_ini and not args.check_bins:
        parser.print_help()
        sys.exit(1)

    results = []
    if args.check_ini:
        results.append(check_ini(args.ini))
    if args.check_bins:
        results.append(check_bins(args.bin_dir))

    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()

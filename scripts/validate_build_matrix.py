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

# Expected output filenames: each must be unique.
EXPECTED_FILENAMES = {
    f"BMCU-DM-PRO-{role.upper().replace('_', '-')}-{length}.bin"
    for role in ROLES
    for length in LENGTHS
}


def _role_label(role: str) -> str:
    """Convert role key to the output label used in filenames (e.g. ams_a -> AMS-A)."""
    return role.upper().replace("_", "-")


def check_ini(ini_path: str) -> bool:
    """Return True iff platformio.ini contains exactly the 96 expected envs (no more, no less).

    The only exempt environment is dm_pro_base (the shared configuration base).
    Any other environment — missing or unexpected — is a hard failure.
    """
    cfg = configparser.ConfigParser(strict=False)
    cfg.read(ini_path)

    present = {s[len("env:"):] for s in cfg.sections() if s.startswith("env:")}
    # dm_pro_base is the shared config base and is not a build target.
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
        # Hard failure: unexpected/legacy environments must be removed.
        print(f"[FAIL] {len(extra)} unexpected environments found in platformio.ini "
              f"(remove or rename them):")
        for e in extra:
            print(f"  - {e}")
        ok = False

    if ok:
        print(f"[OK] platformio.ini contains exactly {len(EXPECTED_ENVS)} expected environments.")
    return ok


def check_bins(bin_dir: str) -> bool:
    """Return True iff bin_dir contains exactly one non-empty firmware.bin per expected env,
    no unexpected environment directories, and all generated filenames are unique.
    """
    ok = True
    missing = []
    empty   = []
    found   = 0

    # ── Expected binaries ────────────────────────────────────────────────────
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

    # ── Unexpected staging directories ───────────────────────────────────────
    expected_set = set(EXPECTED_ENVS)
    if os.path.isdir(bin_dir):
        unexpected_dirs = sorted(
            d for d in os.listdir(bin_dir)
            if os.path.isdir(os.path.join(bin_dir, d)) and d not in expected_set
        )
        if unexpected_dirs:
            print(f"[FAIL] {len(unexpected_dirs)} unexpected directories in {bin_dir}:")
            for d in unexpected_dirs:
                print(f"  - {d}")
            ok = False

    # ── Role/length completeness ──────────────────────────────────────────────
    by_role: dict = {}
    for env in EXPECTED_ENVS:
        # env = dm_pro_{role}_{length}; role may contain underscores (ams_a etc.)
        length = env.split("_")[-1]
        role   = "_".join(env.split("_")[2:-1])
        by_role.setdefault(role, set()).add(length)

    for role in ROLES:
        lengths_found = by_role.get(role, set())
        lengths_expected = set(LENGTHS)
        if lengths_found != lengths_expected:
            missing_l = sorted(lengths_expected - lengths_found)
            extra_l   = sorted(lengths_found - lengths_expected)
            print(f"[FAIL] Role {role}: length mismatch "
                  f"(missing={missing_l}, extra={extra_l})")
            ok = False

    # ── Filename uniqueness ───────────────────────────────────────────────────
    generated_names: list[str] = []
    for env in EXPECTED_ENVS:
        length  = env.split("_")[-1]
        role    = "_".join(env.split("_")[2:-1])
        generated_names.append(f"BMCU-DM-PRO-{_role_label(role)}-{length}.bin")

    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for env, fname in zip(EXPECTED_ENVS, generated_names):
        if fname in seen:
            duplicates.append(f"{fname} <- {env} (already claimed by {seen[fname]})")
        else:
            seen[fname] = env
    if duplicates:
        print(f"[FAIL] {len(duplicates)} duplicate output filenames detected:")
        for d in duplicates:
            print(f"  - {d}")
        ok = False

    if ok:
        print(f"[OK] All {found} firmware binaries present and non-empty.")
        print(f"[OK] All 6 roles have exactly 16 lengths.")
        print(f"[OK] No unexpected staging directories.")
        print(f"[OK] All {len(generated_names)} output filenames are unique.")
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

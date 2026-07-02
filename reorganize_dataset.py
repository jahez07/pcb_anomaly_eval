#!/usr/bin/env python3
"""Reorganize data/curated into the flat curated-dataset layout.

Before:
    data/curated/train/<component_type>/<board>_<NN>_<designator>.<ext>

After:
    data/curated/
    ├── train/<component_type>_<seq>.<ext>
    ├── val_normal/
    ├── val_defective/
    └── metadata.csv

Board number is parsed from the original filename (the two digits before the
designator, e.g. "..._01_R1.jpg" -> board "01") and recorded as board_variant
("board_01"). component_type_id/component_type_name come from the existing
per-component subfolder name. Running the script again after new component
subfolders are added (e.g. more boards) will append to metadata.csv and keep
previously assigned component_type_ids stable.
"""
import csv
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CURATED = ROOT / "data" / "curated"
TRAIN_DIR = CURATED / "train"
VAL_NORMAL_DIR = CURATED / "val_normal"
VAL_DEFECTIVE_DIR = CURATED / "val_defective"
METADATA_PATH = CURATED / "metadata.csv"
METADATA_FIELDS = ["image_path", "component_type_id", "component_type_name", "board_variant", "split"]

FILENAME_RE = re.compile(r"_(\d{2})_([^_/]+)\.(\w+)$")


def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def load_existing_metadata():
    rows = []
    type_ids = {}
    if METADATA_PATH.exists():
        with METADATA_PATH.open(newline="") as f:
            for row in csv.DictReader(f):
                rows.append(row)
                type_ids[row["component_type_name"]] = int(row["component_type_id"])
    return rows, type_ids


def build_plan(component_dirs, type_ids):
    """Validate everything and compute the full set of moves before touching disk."""
    plan = []  # list of (src_path, dest_path, metadata_row)
    dest_names_seen = set()
    next_id = max(type_ids.values(), default=-1) + 1

    for comp_dir in component_dirs:
        type_name = comp_dir.name
        if type_name not in type_ids:
            type_ids[type_name] = next_id
            next_id += 1
        type_id = type_ids[type_name]

        parsed = []
        for f in comp_dir.iterdir():
            if not f.is_file():
                continue
            m = FILENAME_RE.search(f.name)
            if not m:
                raise ValueError(f"Filename does not match expected pattern: {f}")
            board_num, designator, ext = m.groups()
            parsed.append((f, board_num, designator, ext))

        parsed.sort(key=lambda t: (natural_key(t[1]), natural_key(t[2])))

        for idx, (src, board_num, designator, ext) in enumerate(parsed, start=1):
            dest_name = f"{type_name}_{idx:03d}.{ext}"
            if dest_name in dest_names_seen:
                raise FileExistsError(f"Destination name collision: {dest_name}")
            dest_names_seen.add(dest_name)
            dest = TRAIN_DIR / dest_name
            if dest.exists():
                raise FileExistsError(f"Refusing to overwrite existing file: {dest}")

            plan.append((
                src,
                dest,
                {
                    "image_path": f"train/{dest_name}",
                    "component_type_id": type_id,
                    "component_type_name": type_name,
                    "board_variant": f"board_{board_num}",
                    "split": "train",
                },
            ))

    return plan


def main():
    VAL_NORMAL_DIR.mkdir(parents=True, exist_ok=True)
    VAL_DEFECTIVE_DIR.mkdir(parents=True, exist_ok=True)

    component_dirs = sorted(p for p in TRAIN_DIR.iterdir() if p.is_dir())
    if not component_dirs:
        print("No per-component subfolders found under train/ -- nothing to reorganize.")
        return

    rows, type_ids = load_existing_metadata()
    plan = build_plan(component_dirs, type_ids)

    for src, dest, _ in plan:
        shutil.move(str(src), str(dest))

    for comp_dir in component_dirs:
        comp_dir.rmdir()

    rows.extend(row for _, _, row in plan)
    rows.sort(key=lambda r: r["image_path"])

    with METADATA_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=METADATA_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Moved {len(plan)} images from {len(component_dirs)} component folders into {TRAIN_DIR}")
    print(f"Wrote {len(rows)} rows to {METADATA_PATH}")


if __name__ == "__main__":
    main()

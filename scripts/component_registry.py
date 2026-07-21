import sys
import argparse
import pandas as pd

def build_registry(metadata_csv):
    df = pd.read_csv(metadata_csv)

    required = {"component_type_id", "component_type_name"}
    missing = required - set(df.columns)
    if missing:
        sys.exit(f"metadata is missing required columns: {sorted(missing)}")

    pairs = df[["component_type_id", "component_type_name"]].drop_duplicates()
    id_to_names = pairs.groupby("component_type_id")["component_type_name"].apply(set)
    name_to_ids = pairs.groupby("component_type_name")["component_type_id"].apply(set)

    erros = []

    for tid, names in id_to_names.items():
        if len(names) > 1:
            erros.append(f"type_id {tid} has multiple names: {sorted(names)}")
    
    for name, ids in name_to_ids.items():
        if len(ids) > 1:
            erros.append(f"name '{name}' is used by multiple ids: {sorted(ids)}")

    ids = sorted(int(i) for i in id_to_names.index)

    expected = list(range(len(ids)))
    
    if ids != expected:
        erros.append(
            f"type_ids are not contiguous from 0: found {ids}, expected {expected}."
            "Renumber in metadata.csv before proceeding."
        )
    
    if erros:
        print("VALIDATION FAILED:")
        for e in erros:
            print(" -", e)
        sys.exit(1)
    
    return {int(tid): sorted(names)[0] for tid, names in id_to_names.items()}


def write_yaml(registry, out_path):
    lines = [
        "# config/component_types.yaml",
        "component_type:",
    ]
    for tid in sorted(registry):
        lines.append(f"  {tid}: {registry[tid]}")
    lines.append(f"num_types: {len(registry)}")
    text = "\n".join(lines) + "\n"
    with open(out_path, "w") as f:
        f.write(text)
    return text

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--metadata", default="data/metadata.csv")
    ap.add_argument("--out", default="configs/component_types.yaml")
    args = ap.parse_args()

    registry = build_registry(args.metadata)
    text = write_yaml(registry, args.out)

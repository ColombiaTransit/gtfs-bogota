#!/usr/bin/env python3

import pandas as pd

SHAPES_FILE = "gtfs-out/shapes.txt"

print(f"Loading {SHAPES_FILE}")

df = pd.read_csv(
    SHAPES_FILE,
    dtype=str,
    low_memory=False,
)

original_count = len(df)

df["shape_pt_sequence"] = pd.to_numeric(
    df["shape_pt_sequence"]
)

df = df.sort_values(
    ["shape_id", "shape_pt_sequence"]
)

rows = []

removed = 0

for shape_id, group in df.groupby("shape_id", sort=False):

    previous = None

    for _, row in group.iterrows():

        current = (
            row["shape_pt_lat"],
            row["shape_pt_lon"],
            row.get("shape_dist_traveled", "")
        )

        if current == previous:
            removed += 1
            continue

        rows.append(row)
        previous = current

new_df = pd.DataFrame(rows)

new_df.to_csv(
    SHAPES_FILE,
    index=False
)

print(f"Original rows : {original_count:,}")
print(f"Removed rows  : {removed:,}")
print(f"Remaining rows: {len(new_df):,}")

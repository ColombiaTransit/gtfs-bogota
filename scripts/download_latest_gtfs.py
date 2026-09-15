#!/usr/bin/env python3

import os
import sys
import requests
import xml.etree.ElementTree as ET
import pandas as pd
import zipfile
import tempfile
import shutil
import math

from pathlib import Path
from datetime import datetime

BASE_URL = "https://storage.googleapis.com/gtfs-estaticos/"
OUTPUT_FILE = "latest_gtfs.zip"

def sort_stop_times(gtfs_zip):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        with zipfile.ZipFile(gtfs_zip, "r") as zf:
            zf.extractall(tmpdir)

        stop_times = tmpdir / "stop_times.txt"

        if not stop_times.exists():
            print("stop_times.txt not found")
            return

        print("Sorting stop_times.txt...")

        df = pd.read_csv(
            stop_times,
            low_memory=False,
            dtype=str,
            keep_default_na=False,
        )

        df["stop_sequence"] = pd.to_numeric(
            df["stop_sequence"],
            errors="coerce"
        )

        df = df.sort_values(
            ["trip_id", "stop_sequence"],
            kind="stable"
        )

        df.to_csv(
            stop_times,
            index=False
        )

        output_zip = str(gtfs_zip).replace(".zip", "_sorted.zip")

        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in tmpdir.rglob("*"):
                if file.is_file():
                    zf.write(
                        file,
                        file.relative_to(tmpdir)
                    )

        shutil.move(output_zip, gtfs_zip)

        print("stop_times.txt sorted successfully")

def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two coordinates in meters.
    """
    R = 6371000

    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def calculate_shape_distances(gtfs_zip):
    """
    Adds or recalculates shape_dist_traveled
    for all shapes in shapes.txt.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        with zipfile.ZipFile(gtfs_zip, "r") as zf:
            zf.extractall(tmpdir)

        shapes_file = tmpdir / "shapes.txt"

        if not shapes_file.exists():
            print("No shapes.txt found")
            return

        print("Calculating shape_dist_traveled...")

        df = pd.read_csv(
            shapes_file,
            dtype=str,
            keep_default_na=False
        )

        df["shape_pt_sequence"] = (
            pd.to_numeric(df["shape_pt_sequence"])
        )

        df = df.sort_values(
            ["shape_id", "shape_pt_sequence"]
        )

        distances = []

        for shape_id, group in df.groupby("shape_id"):
            cumulative = 0.0
            previous = None

            for _, row in group.iterrows():

                lat = float(row["shape_pt_lat"])
                lon = float(row["shape_pt_lon"])

                if previous:
                    cumulative += haversine(
                        previous[0],
                        previous[1],
                        lat,
                        lon
                    )

                distances.append(cumulative)

                previous = (lat, lon)

        df["shape_dist_traveled"] = [
            round(x, 2)
            for x in distances
        ]

        df.to_csv(
            shapes_file,
            index=False
        )

        output_zip = str(gtfs_zip) + ".tmp"

        with zipfile.ZipFile(
            output_zip,
            "w",
            zipfile.ZIP_DEFLATED
        ) as zf:

            for file in tmpdir.rglob("*"):
                if file.is_file():
                    zf.write(
                        file,
                        file.relative_to(tmpdir)
                    )

        Path(gtfs_zip).unlink()
        Path(output_zip).rename(gtfs_zip)

        print("shape_dist_traveled generated")

def populate_stop_times_shape_distances(gtfs_zip):
    import zipfile
    import tempfile
    from pathlib import Path
    import pandas as pd

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        with zipfile.ZipFile(gtfs_zip, "r") as zf:
            zf.extractall(tmpdir)

        required = [
            "shapes.txt",
            "trips.txt",
            "stops.txt",
            "stop_times.txt"
        ]

        for file in required:
            if not (tmpdir / file).exists():
                print(f"Missing {file}")
                return

        print("Calculating stop_times.shape_dist_traveled...")

        shapes = pd.read_csv(
            tmpdir / "shapes.txt",
            dtype=str,
            keep_default_na=False
        )

        trips = pd.read_csv(
            tmpdir / "trips.txt",
            dtype=str,
            keep_default_na=False
        )

        stops = pd.read_csv(
            tmpdir / "stops.txt",
            dtype=str,
            keep_default_na=False
        )

        stop_times = pd.read_csv(
            tmpdir / "stop_times.txt",
            dtype=str,
            keep_default_na=False
        )

        shapes["shape_pt_sequence"] = pd.to_numeric(
            shapes["shape_pt_sequence"]
        )

        shapes["shape_dist_traveled"] = pd.to_numeric(
            shapes["shape_dist_traveled"],
            errors="coerce"
        )

        trip_shape_map = dict(
            zip(
                trips["trip_id"],
                trips["shape_id"]
            )
        )

        stops_lookup = (
            stops.set_index("stop_id")
            [["stop_lat", "stop_lon"]]
            .to_dict("index")
        )

        shape_lookup = {}

        for shape_id, group in shapes.groupby("shape_id"):
            group = group.sort_values(
                "shape_pt_sequence"
            )

            shape_lookup[shape_id] = [
                (
                    float(row["shape_pt_lat"]),
                    float(row["shape_pt_lon"]),
                    float(row["shape_dist_traveled"])
                )
                for _, row in group.iterrows()
            ]

        def squared_distance(
            lat1,
            lon1,
            lat2,
            lon2
        ):
            return (
                (lat1 - lat2) ** 2 +
                (lon1 - lon2) ** 2
            )

        output_distances = []

        total = len(stop_times)

        for index, row in stop_times.iterrows():

            if index % 10000 == 0:
                print(
                    f"Processed {index:,}/{total:,}"
                )

            trip_id = row["trip_id"]
            stop_id = row["stop_id"]

            shape_id = trip_shape_map.get(trip_id)

            if not shape_id:
                output_distances.append("")
                continue

            stop_info = stops_lookup.get(stop_id)

            if not stop_info:
                output_distances.append("")
                continue

            stop_lat = float(
                stop_info["stop_lat"]
            )

            stop_lon = float(
                stop_info["stop_lon"]
            )

            shape_points = shape_lookup.get(
                shape_id
            )

            if not shape_points:
                output_distances.append("")
                continue

            nearest_distance = None
            nearest_shape_dist = None

            for shp_lat, shp_lon, shape_dist in shape_points:

                d = squared_distance(
                    stop_lat,
                    stop_lon,
                    shp_lat,
                    shp_lon
                )

                if (
                    nearest_distance is None
                    or d < nearest_distance
                ):
                    nearest_distance = d
                    nearest_shape_dist = shape_dist

            output_distances.append(
                round(nearest_shape_dist, 2)
            )

        stop_times[
            "shape_dist_traveled"
        ] = output_distances

        stop_times.to_csv(
            tmpdir / "stop_times.txt",
            index=False
        )

        output_zip = str(gtfs_zip) + ".tmp"

        with zipfile.ZipFile(
            output_zip,
            "w",
            zipfile.ZIP_DEFLATED
        ) as zf:

            for file in tmpdir.rglob("*"):
                if file.is_file():
                    zf.write(
                        file,
                        file.relative_to(tmpdir)
                    )

        Path(gtfs_zip).unlink()
        Path(output_zip).rename(gtfs_zip)

        print(
            "stop_times.shape_dist_traveled generated"
        )

def parse_bucket_listing(xml_content):
    root = ET.fromstring(xml_content)

    ns = {}
    if root.tag.startswith("{"):
        ns_uri = root.tag.split("}")[0].strip("{")
        ns["s3"] = ns_uri

        contents = root.findall("s3:Contents", ns)
        key_tag = "s3:Key"
        modified_tag = "s3:LastModified"
    else:
        contents = root.findall("Contents")
        key_tag = "Key"
        modified_tag = "LastModified"

    latest = None

    for item in contents:
        key = item.findtext(key_tag, namespaces=ns)
        modified = item.findtext(modified_tag, namespaces=ns)

        if not key or not modified:
            continue

        timestamp = datetime.fromisoformat(
            modified.replace("Z", "+00:00")
        )

        if latest is None or timestamp > latest["timestamp"]:
            latest = {
                "key": key,
                "timestamp": timestamp,
            }

    return latest


def main():
    print(f"Fetching bucket index: {BASE_URL}")

    response = requests.get(BASE_URL, timeout=60)
    response.raise_for_status()

    latest = parse_bucket_listing(response.text)

    if not latest:
        print("No GTFS files found")
        sys.exit(1)

    download_url = f"{BASE_URL}{latest['key']}"

    print(f"Latest file: {latest['key']}")
    print(f"Last modified: {latest['timestamp']}")
    print(f"Downloading: {download_url}")

    r = requests.get(download_url, stream=True, timeout=300)
    r.raise_for_status()

    with open(OUTPUT_FILE, "wb") as fh:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                fh.write(chunk)

    size_mb = Path(OUTPUT_FILE).stat().st_size / 1024 / 1024
    print(f"Saved {OUTPUT_FILE} ({size_mb:.2f} MB)")

    print("Optimizing GTFS feed...")
    sort_stop_times(OUTPUT_FILE)
    calculate_shape_distances(OUTPUT_FILE)
    populate_stop_times_shape_distances(OUTPUT_FILE)
    print("Optimization complete")

    with open("latest_gtfs_key.txt", "w") as fh:
        fh.write(latest["key"])

    print("Done")


if __name__ == "__main__":
    main()

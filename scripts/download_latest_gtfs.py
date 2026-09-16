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
    print("Optimization complete")

    with open("latest_gtfs_key.txt", "w") as fh:
        fh.write(latest["key"])

    print("Done")


if __name__ == "__main__":
    main()

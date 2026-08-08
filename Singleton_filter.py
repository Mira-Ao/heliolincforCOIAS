#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import re
from collections import Counter

CLUSTER_RE = re.compile(r"^\s*Cluster\s+(-?\d+)\s*$")


def parse_mpc80_date(line):
    """Return (year, month, day) from an MPC 80-column observation."""
    if len(line) < 32:
        return None
    try:
        year = int(line[15:19])
        month = int(line[20:22])
        day = int(float(line[23:32]))
    except (ValueError, IndexError):
        return None
    return year, month, day


def is_mpc80_observation(line):
    """Identify MPC80 observation lines in finalout_itfMPC80.txt."""
    if len(line) < 80:
        return False
    if line.startswith("#"):
        return False
    if line.startswith("astromRMS"):
        return False
    if line.startswith("Observations:"):
        return False
    if CLUSTER_RE.match(line):
        return False
    return parse_mpc80_date(line) is not None


def finalize_cluster(cluster):
    counts = cluster["nights"]
    cluster["has_singleton_night"] = any(c == 1 for c in counts.values())
    cluster["singleton_nights"] = [
        night for night, count in sorted(counts.items()) if count == 1
    ]


def read_clusters(filename):
    """
    Read finalout_itfMPC80.txt as Cluster blocks.
    A cluster is rejected if any calendar night contains exactly one observation.
    """
    clusters = []
    current = None

    with open(filename, "r", encoding="utf-8-sig", newline="") as f:
        for raw in f:
            line = raw.rstrip("\r\n")
            match = CLUSTER_RE.match(line)

            if match:
                if current is not None:
                    finalize_cluster(current)
                    clusters.append(current)

                current = {
                    "cluster": int(match.group(1)),
                    "lines": [line],
                    "observations": [],
                    "nights": Counter(),
                }
                continue

            if current is None:
                continue

            current["lines"].append(line)

            if is_mpc80_observation(line):
                current["observations"].append(line)
                night = parse_mpc80_date(line)
                if night is not None:
                    current["nights"][night] += 1

    if current is not None:
        finalize_cluster(current)
        clusters.append(current)

    return clusters


def load_linkage(filename):
    with open(filename, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    if not isinstance(data, dict) or not isinstance(data.get("links"), dict):
        raise ValueError('Linkage JSON に "links" がありません。')

    return data


def filter_linkage(data, keep_flags):
    """
    link_1, link_2, ... は finalout の Cluster 出現順と対応すると仮定する。
    残したリンクは MPC 提出用に link_1, link_2, ... と連番にする。
    """
    link_items = list(data["links"].items())

    if len(link_items) != len(keep_flags):
        raise ValueError(
            "Cluster数とlinkageのlink数が一致しません: "
            f"finalout={len(keep_flags)}, linkage={len(link_items)}"
        )

    new_links = {}
    new_number = 1

    for (_, link_data), keep in zip(link_items, keep_flags):
        if keep:
            new_links[f"link_{new_number}"] = link_data
            new_number += 1

    result = dict(data)
    result["links"] = new_links
    return result


def write_filtered_itf(clusters, keep_flags, filename):
    with open(filename, "w", encoding="utf-8", newline="\n") as out:
        for cluster, keep in zip(clusters, keep_flags):
            if keep:
                for line in cluster["lines"]:
                    out.write(line + "\n")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Remove clusters containing a night with exactly one observation "
            "from finalout_itfMPC80.txt and its MPC linkage JSON."
        )
    )

    parser.add_argument("--itf", required=True,
                        help="Input finalout_itfMPC80.txt")
    parser.add_argument("--linkage", required=True,
                        help="Input finalout_itfMPC80_linkage.json")
    parser.add_argument("--output", required=True,
                        help="Filtered ITF output file")
    parser.add_argument("--output-linkage", required=True,
                        help="Filtered MPC linkage JSON output file")

    args = parser.parse_args()

    print("Reading ITF clusters...")
    clusters = read_clusters(args.itf)

    if not clusters:
        raise RuntimeError(f"Cluster が1つも見つかりませんでした: {args.itf}")

    keep_flags = []
    rejected = []

    for cluster in clusters:
        keep = not cluster["has_singleton_night"]
        keep_flags.append(keep)
        if not keep:
            rejected.append(cluster)

    print(f"  Input clusters  : {len(clusters)}")
    print(f"  Kept clusters   : {sum(keep_flags)}")
    print(f"  Removed clusters: {len(rejected)}")

    if rejected:
        print("Removed clusters:")
        for cluster in rejected:
            nights = ", ".join(
                f"{y:04d}-{m:02d}-{d:02d}"
                for y, m, d in cluster["singleton_nights"]
            )
            print(f"  Cluster {cluster['cluster']}: {nights}")

    print("Writing filtered ITF...")
    write_filtered_itf(clusters, keep_flags, args.output)

    print("Reading linkage JSON...")
    linkage = load_linkage(args.linkage)

    print("Writing filtered linkage JSON...")
    filtered = filter_linkage(linkage, keep_flags)

    with open(args.output_linkage, "w", encoding="utf-8", newline="\n") as f:
        json.dump(filtered, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print("Done.")
    print(f"  ITF output     : {args.output}")
    print(f"  Linkage output : {args.output_linkage}")


if __name__ == "__main__":
    main()

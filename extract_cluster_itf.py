#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import json
from collections import defaultdict


def load_clust2det(filename):
    """Read LPclust2det.csv"""
    cluster_to_det = defaultdict(list)

    with open(filename, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        # "#clusternum" と "clusternum" の両方に対応
        if "#clusternum" in reader.fieldnames:
            cluster_col = "#clusternum"
        elif "clusternum" in reader.fieldnames:
            cluster_col = "clusternum"
        else:
            raise ValueError(
                f"Cluster column not found in {filename}. "
                f"Columns are: {reader.fieldnames}"
            )

        for row in reader:
            cluster = int(row[cluster_col])
            det = int(row["detnum"])
            cluster_to_det[cluster].append(det)

    return cluster_to_det


def load_sumfile(filename):
    """Read sumfile.csv and keep astromRMS only"""
    rms = {}

    with open(filename, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        # "#clusternum" と "clusternum" の両方に対応
        if "#clusternum" in reader.fieldnames:
            cluster_col = "#clusternum"
        elif "clusternum" in reader.fieldnames:
            cluster_col = "clusternum"
        else:
            raise ValueError(
                f"Cluster column not found in {filename}. "
                f"Columns are: {reader.fieldnames}"
            )

        for row in reader:
            cluster = int(row[cluster_col])
            rms[cluster] = row["astromRMS"]

    return rms


def load_pairdet(filename):
    """
    detnum -> origindex

    detnum is the row number beginning with 0
    after the header.
    """

    mapping = {}

    with open(filename, newline="") as f:
        reader = csv.DictReader(f)

        for detnum, row in enumerate(reader):
            mapping[detnum] = int(row["origindex"])

    return mapping


def load_itf(filename):
    """
    Read ITF into memory.

    origindex = 0 corresponds to lines[0]
    """

    with open(filename) as f:
        lines = [line.rstrip("\n") for line in f]

    return lines


def main():

    parser = argparse.ArgumentParser(
        description="Extract ITF observations for every HelioLinC cluster."
    )

    parser.add_argument("--clust2det", required=True,
                        help="LPclust2det.csv")

    parser.add_argument("--sum", dest="sumfile",
                        required=True,
                        help="sumfile.csv")

    parser.add_argument("--pairdet", required=True,
                        help="pairdet.csv")

    parser.add_argument("--itf", required=True,
                        help="Original ITF file")

    parser.add_argument("--output", required=True,
                        help="Output text file")

    args = parser.parse_args()

    print("Reading files...")

    cluster_to_det = load_clust2det(args.clust2det)
    rms = load_sumfile(args.sumfile)
    det_to_orig = load_pairdet(args.pairdet)
    itf = load_itf(args.itf)

    print("Writing output...")

    linkage_json={"links":{}}
    link_counter=1

    with open(args.output, "w") as out:

        for cluster in sorted(cluster_to_det.keys()):

            detnums = cluster_to_det[cluster]

            observations = []

            for det in detnums:

                if det not in det_to_orig:
                    print(f"Warning: detnum {det} not found.")
                    continue

                orig = det_to_orig[det]

                if orig < 0 or orig >= len(itf):
                    print(
                        f"Warning: origindex {orig} out of range.")
                    continue

                observations.append((orig, itf[orig]))

            observations.sort(key=lambda x: x[0])

            observations.sort(key=lambda x: x[0])

            # Build one linkage entry per tracklet
            tracklets = {}

            for orig, line in observations:

                tid = line[0:12].replace("*", "").strip()
                date = line[15:32].strip()
                obs = line[77:80].strip()

                year = int(line[15:19])
                month = int(line[20:22])
                day = float(line[23:32])

                timekey = (year, month, day)

                if (tid not in tracklets or
                        timekey < tracklets[tid][0]):

                    tracklets[tid] = (
                        timekey,
                        [tid, date, obs]
                    )

            linkage_json["links"][f"link_{link_counter}"] = {
                "trksubs": [
                    v[1]
                    for v in sorted(
                        tracklets.values(),
                        key=lambda x: x[0]
                    )
                ]
            }

            link_counter += 1
            out.write("#" * 72 + "\n")
            out.write(f"Cluster {cluster}\n")

            if cluster in rms:
                out.write(f"astromRMS   : {rms[cluster]}\n")
            else:
                out.write("astromRMS   : N/A\n")

            out.write(f"Observations: {len(observations)}\n\n")

            for orig, line in observations:
                out.write(line + "\n")

            out.write("\n")

    jsonfile=args.output.rsplit(".",1)[0]+"_linkage.json"
    with open(jsonfile,"w") as jf:
        json.dump(linkage_json,jf,indent=2)
    print("Done.")
    print(f"Linkage JSON written to {jsonfile}")
    print(f"Output written to {args.output}")


if __name__ == "__main__":
    main()
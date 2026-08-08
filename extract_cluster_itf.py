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

    origindex = 0 corresponds to lines[0].
    """
    with open(filename) as f:
        lines = [line.rstrip("\n") for line in f]

    return lines


def mpc80_datetime(line):
    """
    Return:

        (year, month, day, hour, minute, second)

    from an MPC 80-column observation line.

    This is used to find the earliest observation
    for each tracklet on each observing date.
    """
    try:
        year = int(line[15:19])
        month = int(line[20:22])
        day = float(line[23:32])

        hour = int(line[32:34])
        minute = int(line[35:37])
        second = float(line[38:44])

        return (
            year,
            month,
            day,
            hour,
            minute,
            second
        )

    except (ValueError, IndexError):
        return None


def main():

    parser = argparse.ArgumentParser(
        description="Extract ITF observations for every HelioLinC cluster."
    )

    parser.add_argument(
        "--clust2det",
        required=True,
        help="LPclust2det.csv"
    )

    parser.add_argument(
        "--sum",
        dest="sumfile",
        required=True,
        help="sumfile.csv"
    )

    parser.add_argument(
        "--pairdet",
        required=True,
        help="pairdet.csv"
    )

    parser.add_argument(
        "--itf",
        required=True,
        help="Original ITF file"
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output text file"
    )

    args = parser.parse_args()

    print("Reading files...")

    cluster_to_det = load_clust2det(args.clust2det)
    rms = load_sumfile(args.sumfile)
    det_to_orig = load_pairdet(args.pairdet)
    itf = load_itf(args.itf)

    print("Writing output...")

    linkage_json = {
        "links": {}
    }

    link_counter = 1

    with open(args.output, "w") as out:

        for cluster in sorted(cluster_to_det.keys()):

            detnums = cluster_to_det[cluster]

            observations = []

            # ---------------------------------------------------------
            # detnum -> origindex -> ITF observation
            # ---------------------------------------------------------

            for det in detnums:

                if det not in det_to_orig:
                    print(
                        f"Warning: detnum {det} not found."
                    )
                    continue

                orig = det_to_orig[det]

                if orig < 0 or orig >= len(itf):
                    print(
                        f"Warning: origindex {orig} out of range."
                    )
                    continue

                observations.append(
                    (orig, itf[orig])
                )

            # ITFの元の順番に戻す
            observations.sort(
                key=lambda x: x[0]
            )

            # =========================================================
            # MPC linkage JSON
            #
            # 同じ天体名が複数夜に観測されている場合：
            #
            #   H383244 / 2015-03-18 -> 最初の1観測
            #   H383244 / 2015-03-20 -> 最初の1観測
            #
            # のように「天体名＋観測日」ごとに1エントリとする。
            #
            # 例:
            #
            # H383244  2015 03 18.47716
            # H383244  2015 03 18.49910
            # H383244  2015 03 18.53831
            #
            # H383244  2015 03 20.42657
            # H383244  2015 03 20.46619
            #
            # H462554  2015 03 25.45755
            # H462554  2015 03 25.46334
            #
            # =>
            #
            # H383244  2015 03 18.47716
            # H383244  2015 03 20.42657
            # H462554  2015 03 25.45755
            #
            # =========================================================

            tracklets = {}

            for orig, line in observations:

                # MPC object designation
                tid = line[0:12].replace("*", "").strip()

                # MPC observatory code
                obs = line[77:80].strip()

                # Date/time
                dt = mpc80_datetime(line)

                if dt is None:
                    print(
                        "Warning: unable to parse MPC80 "
                        f"date/time for origindex {orig}"
                    )
                    continue

                year, month, day, hour, minute, second = dt

                # MPC linkageに表示する日付文字列。
                #
                # line[15:32] をそのまま使うので、
                # 例えば
                #
                # 2015 03 18.47716
                #
                # となる。
                date = line[15:32].strip()

                # 「同じ天体・同じ観測日」を1グループとする。
                #
                # day は浮動小数点なので、整数部分だけを
                # 観測日として使う。
                night_key = (
                    tid,
                    year,
                    month,
                    int(day)
                )

                # その天体・その日の最初の観測だけ保存する。
                #
                # dt 全体を比較するため、最も早い時刻が残る。
                if (
                    night_key not in tracklets
                    or dt < tracklets[night_key][0]
                ):
                    tracklets[night_key] = (
                        dt,
                        [
                            tid,
                            date,
                            obs
                        ]
                    )

            # 日時順に並べる
            trksubs = [
                item[1]
                for item in sorted(
                    tracklets.values(),
                    key=lambda x: x[0]
                )
            ]

            # MPC linkage JSONへ追加
            linkage_json["links"][
                f"link_{link_counter}"
            ] = {
                "trksubs": trksubs
            }

            link_counter += 1

            # =========================================================
            # ITF text output
            # =========================================================

            out.write(
                "#" * 72 + "\n"
            )

            out.write(
                f"Cluster {cluster}\n"
            )

            if cluster in rms:
                out.write(
                    f"astromRMS   : {rms[cluster]}\n"
                )
            else:
                out.write(
                    "astromRMS   : N/A\n"
                )

            out.write(
                f"Observations: {len(observations)}\n\n"
            )

            for orig, line in observations:
                out.write(
                    line + "\n"
                )

            out.write("\n")

    # =============================================================
    # Linkage JSON output
    # =============================================================

    jsonfile = (
        args.output.rsplit(".", 1)[0]
        + "_linkage.json"
    )

    with open(
        jsonfile,
        "w",
        encoding="utf-8"
    ) as jf:

        json.dump(
            linkage_json,
            jf,
            indent=2,
            ensure_ascii=False
        )

        jf.write("\n")

    print("Done.")
    print(
        f"Linkage JSON written to {jsonfile}"
    )
    print(
        f"Output written to {args.output}"
    )


if __name__ == "__main__":
    main()

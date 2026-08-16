#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import re


CLUSTER_RE = re.compile(r"^\s*Cluster\s+(-?\d+)\s*$")


# ============================================================
# MPC80観測行からトラックレットキーを取得
#
# トラックレット =
#   object ID + 観測日 + observatory code
#
# 時刻は含めない。
# ============================================================

def get_tracklet_key(line):

    if len(line) < 80:
        return None

    try:
        object_id = line[0:12].replace("*", "").strip()

        # MPC80:
        # 15:19 year
        # 20:22 month
        # 23:32 day + fractional day
        year = line[15:19].strip()
        month = line[20:22].strip()
        day = line[23:32].strip()

        obscode = line[77:80].strip()

        if not object_id:
            return None

        if not year or not month or not day:
            return None

        if not obscode:
            return None

        # 日付は整数日にする
        day_number = int(float(day))

        date = (
            f"{int(year):04d} "
            f"{int(month):02d} "
            f"{day_number:02d}"
        )

        return (
            object_id,
            date,
            obscode
        )

    except (ValueError, IndexError):

        return None


# ============================================================
# MPC80観測行かどうか
# ============================================================

def is_observation_line(line):

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

    try:

        int(line[15:19])
        int(line[20:22])
        float(line[23:32])

    except (ValueError, IndexError):

        return False

    return True


# ============================================================
# TXTのClusterを読み込む
# ============================================================

def read_txt_clusters(filename):

    clusters = []

    current = None

    with open(
        filename,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        for raw in f:

            line = raw.rstrip("\r\n")

            match = CLUSTER_RE.match(line)

            # ------------------------------------------------
            # 新しいCluster
            # ------------------------------------------------

            if match:

                if current is not None:

                    clusters.append(
                        current
                    )

                current = {
                    "cluster_number":
                        int(match.group(1)),

                    "lines": [],

                    "tracklets": set()
                }

                current["lines"].append(
                    line
                )

                continue

            # Cluster開始前は無視
            if current is None:
                continue

            current["lines"].append(
                line
            )

            # ------------------------------------------------
            # MPC80観測
            # ------------------------------------------------

            if is_observation_line(line):

                key = get_tracklet_key(
                    line
                )

                if key is not None:

                    current["tracklets"].add(
                        key
                    )

        # 最後のCluster
        if current is not None:

            clusters.append(
                current
            )

    return clusters


# ============================================================
# JSONのトラックレットキー
# ============================================================

def get_json_tracklet_key(trksub):

    if not isinstance(trksub, list):
        return None

    if len(trksub) < 3:
        return None

    object_id = (
        str(trksub[0])
        .replace("*", "")
        .strip()
    )

    date_time = (
        str(trksub[1])
        .strip()
    )

    obscode = (
        str(trksub[2])
        .strip()
    )

    if not object_id:
        return None

    if not date_time:
        return None

    if not obscode:
        return None

    # 例:
    #
    # 2015 03 18.47716
    #
    # →
    #
    # 2015 03 18
    #
    parts = date_time.split()

    if len(parts) >= 3:

        try:

            year = int(parts[0])
            month = int(parts[1])
            day = int(
                float(parts[2])
            )

            date = (
                f"{year:04d} "
                f"{month:02d} "
                f"{day:02d}"
            )

        except ValueError:

            return None

    else:

        return None

    return (
        object_id,
        date,
        obscode
    )


# ============================================================
# JSON読み込み
# ============================================================

def read_json_links(filename):

    with open(
        filename,
        "r",
        encoding="utf-8-sig"
    ) as f:

        data = json.load(f)

    if "links" not in data:

        raise ValueError(
            f"{filename} に 'links' がありません。"
        )

    result = []

    for link_name, link_data in (
        data["links"].items()
    ):

        trksubs = link_data.get(
            "trksubs",
            []
        )

        tracklets = set()

        for trksub in trksubs:

            key = get_json_tracklet_key(
                trksub
            )

            if key is not None:

                tracklets.add(
                    key
                )

        result.append({

            "link_name":
                link_name,

            "data":
                link_data,

            "tracklets":
                tracklets
        })

    return data, result


# ============================================================
# dupremovedファイル名
# ============================================================

def make_dupremoved_filename(
    filename
):

    base, ext = os.path.splitext(
        filename
    )

    return (
        base +
        "_dupremoved" +
        ext
    )


# ============================================================
# 新TXTの重複除去
#
# old_tracklet_setsには、
# 全ての過去TXTの全Clusterを入れる。
#
# したがって、
#
# old_1
# old_2
# old_3
#
# のどれか1つに完全一致すれば削除。
# ============================================================

def filter_txt_clusters(
    new_clusters,
    old_tracklet_sets
):

    kept = []
    removed = []

    for cluster in new_clusters:

        tracklets = (
            cluster["tracklets"]
        )

        duplicate = (
            tracklets
            in old_tracklet_sets
        )

        if duplicate:

            removed.append(
                cluster
            )

        else:

            kept.append(
                cluster
            )

    return kept, removed


# ============================================================
# 新JSONの重複除去
# ============================================================

def filter_json_links(
    new_links,
    old_tracklet_sets
):

    kept = []
    removed = []

    for link in new_links:

        tracklets = (
            link["tracklets"]
        )

        duplicate = (
            tracklets
            in old_tracklet_sets
        )

        if duplicate:

            removed.append(
                link
            )

        else:

            kept.append(
                link
            )

    return kept, removed


# ============================================================
# TXT出力
# ============================================================

def write_txt_clusters(
    clusters,
    filename
):

    with open(
        filename,
        "w",
        encoding="utf-8",
        newline="\n"
    ) as f:

        for cluster in clusters:

            for line in cluster["lines"]:

                f.write(
                    line + "\n"
                )


# ============================================================
# JSON出力
# ============================================================

def write_json_links(
    original_data,
    links,
    filename
):

    output = dict(
        original_data
    )

    new_links = {}

    counter = 1

    for link in links:

        new_links[
            f"link_{counter}"
        ] = link["data"]

        counter += 1

    output["links"] = new_links

    with open(
        filename,
        "w",
        encoding="utf-8",
        newline="\n"
    ) as f:

        json.dump(
            output,
            f,
            indent=2,
            ensure_ascii=False
        )

        f.write("\n")


# ============================================================
# main
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "新しいSingleton_filter出力から、"
            "複数の過去TXTのいずれかに完全一致する"
            "クラスターを除去する。"
        )
    )

    parser.add_argument(
        "--new-txt",
        required=True,
        help="新しいSingleton_filterのTXT"
    )

    parser.add_argument(
        "--new-json",
        required=True,
        help="新しいSingleton_filterのJSON"
    )

    parser.add_argument(
        "--old-txt",
        required=True,
        nargs="+",
        help=(
            "過去のSingleton_filter TXT。"
            "複数指定可能。"
        )
    )

    args = parser.parse_args()

    # ========================================================
    # 過去TXTを全て読み込む
    # ========================================================

    print(
        "Reading old TXT files..."
    )

    old_tracklet_sets = []

    for filename in args.old_txt:

        print(
            f"  Reading: {filename}"
        )

        old_clusters = read_txt_clusters(
            filename
        )

        print(
            f"    clusters: "
            f"{len(old_clusters)}"
        )

        for cluster in old_clusters:

            old_tracklet_sets.append(
                frozenset(
                    cluster["tracklets"]
                )
            )

    # set化して高速化
    old_tracklet_sets = set(
        old_tracklet_sets
    )

    print(
        f"Total old clusters: "
        f"{len(old_tracklet_sets)}"
    )

    # ========================================================
    # 新TXT
    # ========================================================

    print(
        "Reading new TXT..."
    )

    new_clusters = read_txt_clusters(
        args.new_txt
    )

    print(
        f"  New clusters: "
        f"{len(new_clusters)}"
    )

    # ========================================================
    # 新TXTの重複除去
    # ========================================================

    kept_txt, removed_txt = (
        filter_txt_clusters(
            new_clusters,
            old_tracklet_sets
        )
    )

    print(
        f"  Removed duplicate TXT clusters: "
        f"{len(removed_txt)}"
    )

    print(
        f"  Remaining TXT clusters: "
        f"{len(kept_txt)}"
    )

    # ========================================================
    # 新JSON
    # ========================================================

    print(
        "Reading new JSON..."
    )

    new_json_data, new_links = (
        read_json_links(
            args.new_json
        )
    )

    print(
        f"  New JSON links: "
        f"{len(new_links)}"
    )

    # ========================================================
    # 新JSONの重複除去
    # ========================================================

    kept_json, removed_json = (
        filter_json_links(
            new_links,
            old_tracklet_sets
        )
    )

    print(
        f"  Removed duplicate JSON links: "
        f"{len(removed_json)}"
    )

    print(
        f"  Remaining JSON links: "
        f"{len(kept_json)}"
    )

    # ========================================================
    # 出力ファイル名
    # ========================================================

    output_txt = (
        make_dupremoved_filename(
            args.new_txt
        )
    )

    output_json = (
        make_dupremoved_filename(
            args.new_json
        )
    )

    # ========================================================
    # TXT出力
    # ========================================================

    print(
        "Writing:"
    )

    print(
        f"  {output_txt}"
    )

    write_txt_clusters(
        kept_txt,
        output_txt
    )

    # ========================================================
    # JSON出力
    # ========================================================

    print(
        f"  {output_json}"
    )

    write_json_links(
        new_json_data,
        kept_json,
        output_json
    )

    # ========================================================
    # 完了
    # ========================================================

    print()
    print(
        "Done."
    )


if __name__ == "__main__":
    main()
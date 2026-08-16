#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import re
from collections import Counter


# ------------------------------------------------------------
# Cluster行の判定
# ------------------------------------------------------------

CLUSTER_RE = re.compile(r"^\s*Cluster\s+(-?\d+)\s*$")


# ------------------------------------------------------------
# MPC80の日付を取得
# ------------------------------------------------------------

def parse_mpc80_date(line):
    if len(line) < 32:
        return None

    try:
        year = int(line[15:19])
        month = int(line[20:22])
        day = int(float(line[23:32]))
    except (ValueError, IndexError):
        return None

    return year, month, day


# ------------------------------------------------------------
# MPC80観測行かどうか判定
# ------------------------------------------------------------

def is_mpc80_observation(line):

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


# ------------------------------------------------------------
# クラスターのSingleton判定
# ------------------------------------------------------------

def finalize_cluster(cluster):

    counts = cluster["nights"]

    # どこか1夜でも観測数が1ならSingleton cluster
    cluster["has_singleton_night"] = any(
        count == 1
        for count in counts.values()
    )

    cluster["singleton_nights"] = [
        night
        for night, count in sorted(counts.items())
        if count == 1
    ]


# ------------------------------------------------------------
# finalout_itfMPC80.txtをCluster単位で読み込む
# ------------------------------------------------------------

def read_clusters(filename):

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

            # 新しいClusterが始まった
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

            # Cluster開始前の行は無視
            if current is None:
                continue

            current["lines"].append(line)

            # MPC80観測行
            if is_mpc80_observation(line):

                current["observations"].append(line)

                night = parse_mpc80_date(line)

                if night is not None:
                    current["nights"][night] += 1

    # 最後のCluster
    if current is not None:

        finalize_cluster(current)
        clusters.append(current)

    return clusters


# ------------------------------------------------------------
# linkage JSON読み込み
# ------------------------------------------------------------

def load_linkage(filename):

    with open(
        filename,
        "r",
        encoding="utf-8-sig"
    ) as f:

        data = json.load(f)

    if (
        not isinstance(data, dict)
        or not isinstance(data.get("links"), dict)
    ):
        raise ValueError(
            'Linkage JSON に "links" がありません。'
        )

    return data


# ------------------------------------------------------------
# linkage JSONからSingleton clusterを除外
# ------------------------------------------------------------

def filter_linkage(data, keep_flags):

    link_items = list(
        data["links"].items()
    )

    # --------------------------------------------------------
    # Cluster数とlink数が一致しない場合でも処理を続行する。
    #
    # keep_flags:
    #   finalout_itfMPC80.txt に存在するClusterのSingleton判定
    #
    # link_items:
    #   linkage JSONのlink_1, link_2, ...
    #
    # 両者のうち対応可能な範囲だけを処理する。
    # --------------------------------------------------------

    if len(link_items) != len(keep_flags):

        print(
            "WARNING: Cluster数とlinkageのlink数が一致しません。"
        )

        print(
            f"  finalout clusters = {len(keep_flags)}"
        )

        print(
            f"  linkage links     = {len(link_items)}"
        )

        if len(link_items) > len(keep_flags):

            print(
                f"  linkage側に "
                f"{len(link_items) - len(keep_flags)} "
                f"個の余分なlinkがあります。"
            )

        else:

            print(
                f"  linkage側に "
                f"{len(keep_flags) - len(link_items)} "
                f"個のlinkが不足しています。"
            )

    new_links = {}
    new_number = 1

    # 対応できる範囲だけ処理
    n = min(
        len(link_items),
        len(keep_flags)
    )

    for i in range(n):

        _, link_data = link_items[i]

        keep = keep_flags[i]

        if keep:

            new_links[
                f"link_{new_number}"
            ] = link_data

            new_number += 1

    result = dict(data)

    result["links"] = new_links

    return result


# ------------------------------------------------------------
# filtered ITFを書き出す
#
# 追加仕様：
# Singleton除外後に残った各Clusterについて、
# そのCluster内で最初に出現した観測を1行ずつ
# ファイル末尾に追加する。
# ------------------------------------------------------------

def write_filtered_itf(
    clusters,
    keep_flags,
    filename
):

    # 各Clusterの最初の観測をここに保存
    first_observations = []

    with open(
        filename,
        "w",
        encoding="utf-8",
        newline="\n"
    ) as out:

        # ====================================================
        # 通常のfiltered ITF
        # ====================================================

        for cluster, keep in zip(
            clusters,
            keep_flags
        ):

            # Singletonを含むClusterは除外
            if not keep:
                continue

            # Cluster本体を書き出す
            for line in cluster["lines"]:
                out.write(line + "\n")

            # ------------------------------------------------
            # このClusterで最初に出現した観測を保存
            # ------------------------------------------------

            if cluster["observations"]:

                first_observations.append(
                    cluster["observations"][0]
                )

        # ====================================================
        # ファイル末尾に各Clusterの最初の観測を追加
        # ====================================================

        if first_observations:

            out.write("\n")

            out.write(
                "# First observation of each kept cluster\n"
            )

            for line in first_observations:

                out.write(
                    line + "\n"
                )


# ------------------------------------------------------------
# main
# ------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description=(
            "finalout_itfMPC80.txtから、"
            "1夜に1観測しかない夜を含むClusterを除外し、"
            "対応するMPC linkage JSONもフィルタする。"
            "さらにfiltered ITFの末尾に、"
            "各Clusterの最初の観測を1行ずつ追加する。"
        )
    )

    parser.add_argument(
        "--itf",
        required=True,
        help="入力 finalout_itfMPC80.txt"
    )

    parser.add_argument(
        "--linkage",
        required=True,
        help="入力 finalout_itfMPC80_linkage.json"
    )

    parser.add_argument(
        "--output",
        required=True,
        help="filtered ITFの出力ファイル"
    )

    parser.add_argument(
        "--output-linkage",
        required=True,
        help="filtered linkage JSONの出力ファイル"
    )

    args = parser.parse_args()

    # ========================================================
    # ITF読み込み
    # ========================================================

    print("Reading ITF clusters...")

    clusters = read_clusters(
        args.itf
    )

    if not clusters:

        raise RuntimeError(
            f"Cluster が1つも見つかりませんでした: "
            f"{args.itf}"
        )

    # ========================================================
    # Singleton判定
    # ========================================================

    keep_flags = []
    rejected = []

    for cluster in clusters:

        keep = not cluster[
            "has_singleton_night"
        ]

        keep_flags.append(
            keep
        )

        if not keep:

            rejected.append(
                cluster
            )

    # ========================================================
    # 結果表示
    # ========================================================

    print(
        f"  Input clusters  : "
        f"{len(clusters)}"
    )

    print(
        f"  Kept clusters   : "
        f"{sum(keep_flags)}"
    )

    print(
        f"  Removed clusters: "
        f"{len(rejected)}"
    )

    if rejected:

        print(
            "Removed clusters:"
        )

        for cluster in rejected:

            nights = ", ".join(
                f"{year:04d}-{month:02d}-{day:02d}"
                for year, month, day
                in cluster[
                    "singleton_nights"
                ]
            )

            print(
                f"  Cluster "
                f"{cluster['cluster']}: "
                f"{nights}"
            )

    # ========================================================
    # filtered ITF出力
    # ========================================================

    print(
        "Writing filtered ITF..."
    )

    write_filtered_itf(
        clusters,
        keep_flags,
        args.output
    )

    # ========================================================
    # linkage JSON読み込み
    # ========================================================

    print(
        "Reading linkage JSON..."
    )

    linkage = load_linkage(
        args.linkage
    )

    # ========================================================
    # linkage JSONフィルタ
    # ========================================================

    print(
        "Writing filtered linkage JSON..."
    )

    filtered = filter_linkage(
        linkage,
        keep_flags
    )

    with open(
        args.output_linkage,
        "w",
        encoding="utf-8",
        newline="\n"
    ) as f:

        json.dump(
            filtered,
            f,
            indent=2,
            ensure_ascii=False
        )

        f.write("\n")

    # ========================================================
    # 完了
    # ========================================================

    print("Done.")

    print(
        f"  ITF output     : "
        f"{args.output}"
    )

    print(
        f"  Linkage output : "
        f"{args.output_linkage}"
    )

    print(
        "  各残存Clusterの最初の観測を"
        "ITF末尾に追加しました。"
    )


if __name__ == "__main__":
    main()
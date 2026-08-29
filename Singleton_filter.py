#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import re
from collections import Counter
from datetime import date


CLUSTER_RE = re.compile(r"^\s*Cluster\s+(-?\d+)\s*$")


# ------------------------------------------------------------
# MPC80の日付を取得
# ------------------------------------------------------------

def parse_mpc80_date(line):
    """Return (year, month, day) from an MPC80 observation."""
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


# ------------------------------------------------------------
# クラスターの判定
# ------------------------------------------------------------

def finalize_cluster(cluster):

    counts = cluster["nights"]

    # --------------------------------------------------------
    # 条件1:
    # どこか1夜でも観測数が1ならSingleton cluster
    # --------------------------------------------------------

    cluster["has_singleton_night"] = any(
        count == 1
        for count in counts.values()
    )

    cluster["singleton_nights"] = [
        night
        for night, count in sorted(counts.items())
        if count == 1
    ]

    # --------------------------------------------------------
    # 条件2:
    # 3夜しかないクラスターで、
    # 最初と最後の夜が17日を超えて離れていたら除外
    # --------------------------------------------------------

    nights = sorted(counts.keys())

    cluster["has_long_3night_span"] = False
    cluster["three_night_span"] = None

    if len(nights) == 3:

        first_night = date(
            nights[0][0],
            nights[0][1],
            nights[0][2]
        )

        last_night = date(
            nights[-1][0],
            nights[-1][1],
            nights[-1][2]
        )

        span_days = (last_night - first_night).days

        cluster["three_night_span"] = span_days

        if span_days > 17:
            cluster["has_long_3night_span"] = True


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

            # ------------------------------------------------
            # 新しいClusterが始まった
            # ------------------------------------------------

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

            # ------------------------------------------------
            # MPC80観測行
            # ------------------------------------------------

            if is_mpc80_observation(line):

                current["observations"].append(line)

                night = parse_mpc80_date(line)

                if night is not None:
                    current["nights"][night] += 1

    # --------------------------------------------------------
    # 最後のCluster
    # --------------------------------------------------------

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
# linkage JSONからClusterを除外
# ------------------------------------------------------------

def filter_linkage(data, keep_flags):

    """
    link_1, link_2, ... は finalout の Cluster 出現順と
    対応すると仮定する。

    ただし、finaloutのCluster数とlinkageのlink数が
    一致しない場合もエラーにはせず、
    存在するlinkだけを処理する。
    """

    link_items = list(data["links"].items())

    new_links = {}
    new_number = 1

    # --------------------------------------------------------
    # 一致する範囲だけ処理
    # --------------------------------------------------------

    n = min(len(link_items), len(keep_flags))

    for i in range(n):

        _, link_data = link_items[i]
        keep = keep_flags[i]

        if keep:

            new_links[
                f"link_{new_number}"
            ] = link_data

            new_number += 1

    # --------------------------------------------------------
    # linkageのほうが多い場合
    #
    # 対応するCluster情報がないため、
    # 残りのlinkはそのまま保持する。
    #
    # これにより、
    # 「Cluster数とlinkageのlink数が一致しない」
    # 場合でも停止しない。
    # --------------------------------------------------------

    if len(link_items) > len(keep_flags):

        for i in range(n, len(link_items)):

            _, link_data = link_items[i]

            new_links[
                f"link_{new_number}"
            ] = link_data

            new_number += 1

    result = dict(data)
    result["links"] = new_links

    return result


# ------------------------------------------------------------
# filtered ITFを書き出す
# ------------------------------------------------------------

def write_filtered_itf(
    clusters,
    keep_flags,
    filename
):
    """
    残ったClusterをそのまま出力した後、
    ファイル末尾に各Clusterの最初の観測を1行ずつ追加する。
    """

    with open(
        filename,
        "w",
        encoding="utf-8",
        newline="\n"
    ) as out:

        # ----------------------------------------------------
        # まず、残ったClusterを通常どおり出力
        # ----------------------------------------------------

        for cluster, keep in zip(
            clusters,
            keep_flags
        ):

            if keep:
                for line in cluster["lines"]:
                    out.write(line + "\n")

        # ----------------------------------------------------
        # ファイル末尾に各Clusterの最初の観測を追加
        # ----------------------------------------------------

        out.write("\n")
        out.write("########################################################################\n")
        out.write("\n")
        out.write("# First observation of each kept cluster\n")

        for cluster, keep in zip(
            clusters,
            keep_flags
        ):

            if not keep:
                continue

            # 観測が存在するClusterだけ
            if cluster["observations"]:

                # 各Clusterの最初の観測
                first_observation = cluster["observations"][0]

                out.write(first_observation + "\n")


# ------------------------------------------------------------
# メイン
# ------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Remove clusters containing a singleton night, "
            "and remove 3-night clusters whose first-to-last "
            "night span exceeds 17 days."
        )
    )

    parser.add_argument(
        "--itf",
        required=True,
        help="Input finalout_itfMPC80.txt"
    )

    parser.add_argument(
        "--linkage",
        required=True,
        help="Input finalout_itfMPC80_linkage.json"
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Filtered ITF output file"
    )

    parser.add_argument(
        "--output-linkage",
        required=True,
        help="Filtered MPC linkage JSON output file"
    )

    args = parser.parse_args()

    # --------------------------------------------------------
    # 読み込み
    # --------------------------------------------------------

    print("Reading ITF clusters...")

    clusters = read_clusters(args.itf)

    if not clusters:

        raise RuntimeError(
            f"Cluster が1つも見つかりませんでした: "
            f"{args.itf}"
        )

    print(
        f"  Input clusters: {len(clusters)}"
    )

    # --------------------------------------------------------
    # Clusterごとの判定
    # --------------------------------------------------------

    keep_flags = []

    singleton_rejected = []
    long_3night_rejected = []

    for cluster in clusters:

        # ----------------------------------------------------
        # Singleton条件
        # ----------------------------------------------------

        if cluster["has_singleton_night"]:

            keep = False
            singleton_rejected.append(cluster)

        # ----------------------------------------------------
        # 3夜・17日超過条件
        # ----------------------------------------------------

        elif cluster["has_long_3night_span"]:

            keep = False
            long_3night_rejected.append(cluster)

        # ----------------------------------------------------
        # その他は保持
        # ----------------------------------------------------

        else:

            keep = True

        keep_flags.append(keep)

    # --------------------------------------------------------
    # 結果表示
    # --------------------------------------------------------

    print(
        f"  Kept clusters             : "
        f"{sum(keep_flags)}"
    )

    print(
        f"  Removed (singleton night) : "
        f"{len(singleton_rejected)}"
    )

    print(
        f"  Removed (3 nights > 17 d) : "
        f"{len(long_3night_rejected)}"
    )

    print(
        f"  Total removed             : "
        f"{len(clusters) - sum(keep_flags)}"
    )

    # --------------------------------------------------------
    # 3夜17日超過Clusterの詳細表示
    # --------------------------------------------------------

    if long_3night_rejected:

        print("")
        print(
            "3-night clusters removed because "
            "first-to-last span > 17 days:"
        )

        for cluster in long_3night_rejected:

            nights = sorted(
                cluster["nights"].keys()
            )

            print(
                f"  Cluster {cluster['cluster']}: "
                f"{nights[0]} -> {nights[-1]}, "
                f"span = {cluster['three_night_span']} days"
            )

    # --------------------------------------------------------
    # ITF出力
    # --------------------------------------------------------

    write_filtered_itf(
        clusters,
        keep_flags,
        args.output
    )

    print("")
    print(
        f"Filtered ITF written to: "
        f"{args.output}"
    )

    # --------------------------------------------------------
    # linkage JSON
    # --------------------------------------------------------

    print("Reading linkage JSON...")

    linkage = load_linkage(
        args.linkage
    )

    print(
        f"  Linkage entries: "
        f"{len(linkage['links'])}"
    )

    filtered_linkage = filter_linkage(
        linkage,
        keep_flags
    )

    # --------------------------------------------------------
    # JSON出力
    # --------------------------------------------------------

    with open(
        args.output_linkage,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            filtered_linkage,
            f,
            indent=2,
            ensure_ascii=False
        )

        f.write("\n")

    print(
        f"Filtered linkage written to: "
        f"{args.output_linkage}"
    )

    print("")
    print("Done.")


if __name__ == "__main__":
    main()
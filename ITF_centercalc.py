#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import math


# ============================================================
# MPC80 / OBS80 から RA, Dec を読み取る
# ============================================================

def parse_mpc80_line(line):

    if len(line) < 80:
        return None

    try:
        # RA
        rah = float(line[32:34])
        ram = float(line[35:37])
        ras = float(line[38:44])

        # Dec
        sign = line[44]

        if sign not in ("+", "-"):
            return None

        decd = float(line[45:47])
        decm = float(line[48:50])
        decs = float(line[51:56])

        ra = (
            15.0 * rah
            + ram / 4.0
            + ras / 240.0
        )

        dec = (
            decd
            + decm / 60.0
            + decs / 3600.0
        )

        if sign == "-":
            dec *= -1.0

        if not (0.0 <= ra <= 360.0):
            return None

        if not (-90.0 <= dec <= 90.0):
            return None

        return ra, dec

    except (ValueError, IndexError):

        return None


# ============================================================
# 角距離
# ============================================================

def angular_distance(ra1, dec1, ra2, dec2):

    ra1 = math.radians(ra1)
    dec1 = math.radians(dec1)

    ra2 = math.radians(ra2)
    dec2 = math.radians(dec2)

    cos_d = (
        math.sin(dec1) * math.sin(dec2)
        + math.cos(dec1)
        * math.cos(dec2)
        * math.cos(ra1 - ra2)
    )

    # 浮動小数点誤差対策
    cos_d = max(-1.0, min(1.0, cos_d))

    return math.degrees(
        math.acos(cos_d)
    )


# ============================================================
# 観測領域を1度以内の連結成分として分類
#
# A-B が1度以内
# B-C が1度以内
# なら、A-B-C は同じグループとする。
# ============================================================

def find_groups(observations):

    n = len(observations)

    parent = list(range(n))

    def find(x):

        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]

        return x

    def union(a, b):

        ra = find(a)
        rb = find(b)

        if ra != rb:
            parent[rb] = ra

    # 全観測の組み合わせを調べる
    for i in range(n):

        ra1, dec1 = observations[i]

        for j in range(i + 1, n):

            ra2, dec2 = observations[j]

            distance = angular_distance(
                ra1,
                dec1,
                ra2,
                dec2
            )

            if distance <= 1.0:

                union(i, j)

    # グループ化
    groups = {}

    for i in range(n):

        root = find(i)

        if root not in groups:
            groups[root] = []

        groups[root].append(i)

    # 大きい順
    result = sorted(
        groups.values(),
        key=len,
        reverse=True
    )

    return result


# ============================================================
# 球面上の平均座標から中心を求める
#
# RAの0/360度境界にも対応
# ============================================================

def calculate_center(observations):

    x = 0.0
    y = 0.0
    z = 0.0

    for ra, dec in observations:

        ra_rad = math.radians(ra)
        dec_rad = math.radians(dec)

        x += (
            math.cos(dec_rad)
            * math.cos(ra_rad)
        )

        y += (
            math.cos(dec_rad)
            * math.sin(ra_rad)
        )

        z += math.sin(dec_rad)

    x /= len(observations)
    y /= len(observations)
    z /= len(observations)

    ra = math.atan2(y, x)

    if ra < 0:
        ra += 2.0 * math.pi

    hyp = math.sqrt(
        x * x + y * y
    )

    dec = math.atan2(
        z,
        hyp
    )

    return (
        math.degrees(ra),
        math.degrees(dec)
    )


# ============================================================
# RAをhh mm ss.ss に変換
# ============================================================

def format_ra(ra):

    total_seconds = ra / 15.0 * 3600.0

    h = int(
        total_seconds // 3600
    )

    total_seconds -= h * 3600

    m = int(
        total_seconds // 60
    )

    s = (
        total_seconds
        - m * 60
    )

    # 24h境界対策
    if h >= 24:
        h -= 24

    return (
        f"{h:02d} "
        f"{m:02d} "
        f"{s:05.2f}"
    )


# ============================================================
# Decをdd mm ss.ss に変換
# ============================================================

def format_dec(dec):

    sign = "+"

    if dec < 0:
        sign = "-"
        dec = abs(dec)

    d = int(dec)

    remainder = (
        dec - d
    ) * 60.0

    m = int(remainder)

    s = (
        remainder - m
    ) * 60.0

    return (
        f"{sign}{d:02d} "
        f"{m:02d} "
        f"{s:05.2f}"
    )


# ============================================================
# 中心から各観測までの距離を計算
# ============================================================

def calculate_radii(
    observations,
    center_ra,
    center_dec
):

    distances = []

    for ra, dec in observations:

        distance = angular_distance(
            center_ra,
            center_dec,
            ra,
            dec
        )

        distances.append(
            distance
        )

    distances.sort()

    def percentile(p):

        if len(distances) == 1:
            return distances[0]

        # nearest-rank方式
        index = math.ceil(
            p * len(distances)
        ) - 1

        index = max(
            0,
            min(index, len(distances) - 1)
        )

        return distances[index]

    return (
        percentile(0.80),
        percentile(0.95),
        percentile(0.99)
    )


# ============================================================
# ファイル読み込み
# ============================================================

def read_observations(filename):

    observations = []

    total_lines = 0
    ignored_lines = 0

    with open(
        filename,
        "r",
        encoding="utf-8-sig",
        errors="replace"
    ) as f:

        for line in f:

            total_lines += 1

            line = line.rstrip("\r\n")

            result = parse_mpc80_line(
                line
            )

            if result is None:

                ignored_lines += 1
                continue

            observations.append(
                result
            )

    return (
        observations,
        total_lines,
        ignored_lines
    )


# ============================================================
# 1グループについて結果を表示
# ============================================================

def print_group_result(
    group_number,
    group,
    all_count,
    observations
):

    group_observations = [
        observations[i]
        for i in group
    ]

    count = len(
        group_observations
    )

    percentage = (
        100.0
        * count
        / all_count
    )

    center_ra, center_dec = (
        calculate_center(
            group_observations
        )
    )

    r80, r95, r99 = (
        calculate_radii(
            group_observations,
            center_ra,
            center_dec
        )
    )

    print()
    print(
        "========================================"
    )

    print(
        f"Observation group {group_number}"
    )

    print(
        "========================================"
    )

    print(
        f"Observations       : {count}"
    )

    print(
        f"largest group/all  : "
        f"{count}/{all_count} "
        f"({percentage:.2f}%)"
    )

    print(
        f"Center RA          : "
        f"{format_ra(center_ra)}"
    )

    print(
        f"Center Dec         : "
        f"{format_dec(center_dec)}"
    )

    print(
        f"Radius containing 80% : "
        f"{r80:.4f} deg"
    )

    print(
        f"Radius containing 95% : "
        f"{r95:.4f} deg"
    )

    print(
        f"Radius containing 99% : "
        f"{r99:.4f} deg"
    )


# ============================================================
# main
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "OBS80/ITF形式の観測から、"
            "1度以内で連結された観測領域を分類し、"
            "主要領域の中心座標と80/95/99%半径を計算します。"
        )
    )

    parser.add_argument(
        "input_file",
        help="入力OBS80/ITFファイル"
    )

    args = parser.parse_args()

    print(
        f"Reading: {args.input_file}"
    )

    (
        observations,
        total_lines,
        ignored_lines
    ) = read_observations(
        args.input_file
    )

    if len(observations) == 0:

        print(
            "有効なMPC80形式の観測がありません。"
        )

        return

    print(
        f"Total input lines : {total_lines}"
    )

    print(
        f"Valid observations: "
        f"{len(observations)}"
    )

    print(
        f"Ignored lines     : "
        f"{ignored_lines}"
    )

    print()
    print(
        "Finding observation groups..."
    )

    groups = find_groups(
        observations
    )

    print(
        f"Number of groups: "
        f"{len(groups)}"
    )

    # --------------------------------------------------------
    # 第1グループ
    # --------------------------------------------------------

    largest_count = len(
        groups[0]
    )

    largest_percentage = (
        100.0
        * largest_count
        / len(observations)
    )

    print_group_result(
        1,
        groups[0],
        len(observations),
        observations
    )

    # --------------------------------------------------------
    # 最大グループが90%未満なら第2グループも表示
    # --------------------------------------------------------

    if (
        largest_percentage
        < 90.0
        and len(groups) >= 2
    ):

        print()

        print(
            "Largest group is less than "
            "90% of all observations."
        )

        print(
            "Calculating the second-largest "
            "group as well."
        )

        print_group_result(
            2,
            groups[1],
            len(observations),
            observations
        )

    elif (
        largest_percentage < 90.0
        and len(groups) < 2
    ):

        print()
        print(
            "Largest group is less than 90%, "
            "but there is no second group."
        )

    print()


if __name__ == "__main__":
    main()
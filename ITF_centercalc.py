#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import math
import sys
from collections import defaultdict

# 同一観測領域とみなす最大角距離
GROUP_RADIUS_DEG = 1.0


def angular_distance_deg(ra1, dec1, ra2, dec2):
    """2つの天球座標間の角距離を度で返す。"""

    ra1 = math.radians(ra1)
    dec1 = math.radians(dec1)
    ra2 = math.radians(ra2)
    dec2 = math.radians(dec2)

    cosang = (
        math.sin(dec1) * math.sin(dec2)
        + math.cos(dec1)
        * math.cos(dec2)
        * math.cos(ra1 - ra2)
    )

    cosang = max(-1.0, min(1.0, cosang))

    return math.degrees(math.acos(cosang))


def parse_mpc80(line):
    """
    MPC 80-column形式を解析する。

    戻り値:
        (RA_deg, Dec_deg)

    MPC80として不正な場合:
        None
    """

    if len(line) < 80:
        return None

    try:
        # ---------------------------------------------------------
        # 日付
        # ---------------------------------------------------------
        year = int(line[15:19])
        month = int(line[20:22])
        day = float(line[23:32])

        if year < 1900:
            return None

        if not (1 <= month <= 12):
            return None

        if not (1 <= day <= 32):
            return None

        # ---------------------------------------------------------
        # 赤経
        # hh mm ss.ss
        # ---------------------------------------------------------
        hour = int(line[32:34])
        minute = int(line[35:37])
        second = float(line[38:44])

        if not (0 <= hour < 24):
            return None

        if not (0 <= minute < 60):
            return None

        if not (0 <= second < 60):
            return None

        ra_deg = 15.0 * (
            hour
            + minute / 60.0
            + second / 3600.0
        )

        # ---------------------------------------------------------
        # 赤緯
        # +/-dd mm ss.s
        # ---------------------------------------------------------
        sign = line[44]

        if sign not in ("+", "-"):
            return None

        degree = int(line[45:47])
        minute = int(line[48:50])
        second = float(line[51:56])

        if not (0 <= degree <= 90):
            return None

        if not (0 <= minute < 60):
            return None

        if not (0 <= second < 60):
            return None

        if degree == 90 and (
            minute != 0 or second != 0
        ):
            return None

        dec_deg = (
            degree
            + minute / 60.0
            + second / 3600.0
        )

        if sign == "-":
            dec_deg *= -1.0

        return ra_deg, dec_deg

    except (
        ValueError,
        IndexError,
        OverflowError
    ):
        return None


class UnionFind:
    """連結成分を求めるためのUnion-Find。"""

    def __init__(self, n):
        self.parent = list(range(n))
        self.size = [1] * n

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[
                self.parent[x]
            ]
            x = self.parent[x]

        return x

    def union(self, a, b):

        a = self.find(a)
        b = self.find(b)

        if a == b:
            return

        if self.size[a] < self.size[b]:
            a, b = b, a

        self.parent[b] = a
        self.size[a] += self.size[b]


def sky_bin(ra_deg, dec_deg):
    """
    近傍探索用の1度グリッド。

    RAは0/360度境界を考慮する。
    """

    ra_bin = int(ra_deg) % 360
    dec_bin = int(math.floor(dec_deg)) + 90

    return ra_bin, dec_bin


def neighboring_bins(ra_bin, dec_bin):
    """
    現在のグリッドと隣接するグリッドを返す。
    """

    for dra in (-1, 0, 1):

        ra = (ra_bin + dra) % 360

        for ddec in (-1, 0, 1):

            dec = dec_bin + ddec

            if 0 <= dec <= 180:
                yield ra, dec


def build_groups(observations):
    """
    「1度以内」という関係で観測を連結し、
    連結成分を観測領域として返す。

    例えば

        A -- 0.8 deg -- B -- 0.7 deg -- C

    なら、A-Cが1度を超えていても
    A, B, Cは同じ観測領域になる。
    """

    n = len(observations)

    uf = UnionFind(n)

    bins = defaultdict(list)

    # 観測を空間グリッドへ登録
    for i, (ra, dec) in enumerate(observations):

        bins[
            sky_bin(ra, dec)
        ].append(i)

    # 近傍観測を探索
    for i, (ra, dec) in enumerate(observations):

        rb, db = sky_bin(ra, dec)

        for b in neighboring_bins(rb, db):

            for j in bins.get(b, ()):

                if j <= i:
                    continue

                ra2, dec2 = observations[j]

                distance = angular_distance_deg(
                    ra,
                    dec,
                    ra2,
                    dec2
                )

                if distance <= GROUP_RADIUS_DEG:
                    uf.union(i, j)

    groups = defaultdict(list)

    for i in range(n):
        groups[
            uf.find(i)
        ].append(i)

    return sorted(
        groups.values(),
        key=len,
        reverse=True
    )


def spherical_mean(observations, indices):
    """
    天球上の単位ベクトルを平均して中心座標を求める。
    """

    x = 0.0
    y = 0.0
    z = 0.0

    for i in indices:

        ra, dec = observations[i]

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

    norm = math.sqrt(
        x * x
        + y * y
        + z * z
    )

    if norm == 0:
        raise ValueError(
            "Spherical mean is undefined."
        )

    x /= norm
    y /= norm
    z /= norm

    ra = math.degrees(
        math.atan2(y, x)
    ) % 360.0

    dec = math.degrees(
        math.asin(
            max(-1.0, min(1.0, z))
        )
    )

    return ra, dec


def format_ra(ra_deg):
    """
    赤経を

        hh mm ss.ss

    に変換する。
    """

    total_seconds = (
        ra_deg / 15.0
    ) * 3600.0

    total_seconds %= (
        24.0 * 3600.0
    )

    hour = int(
        total_seconds // 3600
    )

    total_seconds -= (
        hour * 3600
    )

    minute = int(
        total_seconds // 60
    )

    second = (
        total_seconds
        - minute * 60
    )

    return (
        f"{hour:02d} "
        f"{minute:02d} "
        f"{second:05.2f}"
    )


def format_dec(dec_deg):
    """
    赤緯を

        +/-dd mm ss.s

    に変換する。
    """

    sign = (
        "+"
        if dec_deg >= 0
        else "-"
    )

    value = abs(dec_deg)

    degree = int(value)

    value = (
        value - degree
    ) * 60.0

    minute = int(value)

    second = (
        value - minute
    ) * 60.0

    return (
        f"{sign}"
        f"{degree:02d} "
        f"{minute:02d} "
        f"{second:04.1f}"
    )


def percentile(values, percentage):
    """
    線形補間によるパーセンタイル。
    """

    if not values:
        raise ValueError(
            "Cannot calculate percentile "
            "of an empty list."
        )

    if len(values) == 1:
        return values[0]

    position = (
        (len(values) - 1)
        * percentage
        / 100.0
    )

    lower = int(
        math.floor(position)
    )

    upper = int(
        math.ceil(position)
    )

    if lower == upper:
        return values[lower]

    fraction = position - lower

    return (
        values[lower]
        + (
            values[upper]
            - values[lower]
        )
        * fraction
    )


def write_output(
    filename,
    input_file,
    total_lines,
    valid_count,
    ignored_count,
    group_count,
    main_count,
    main_percentage,
    center_ra,
    center_dec,
    radii
):

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            "ITF_centercalc result\n"
        )

        f.write(
            "====================\n\n"
        )

        f.write(
            f"Input file: {input_file}\n"
        )

        f.write(
            f"Total input lines: "
            f"{total_lines}\n"
        )

        f.write(
            f"Valid MPC80 observations: "
            f"{valid_count}\n"
        )

        f.write(
            f"Ignored invalid lines: "
            f"{ignored_count}\n"
        )

        f.write(
            f"Number of observation groups: "
            f"{group_count}\n\n"
        )

        f.write(
            "Main observation region\n"
        )

        f.write(
            "-----------------------\n"
        )

        f.write(
            f"largest group/all = "
            f"{main_percentage:.4f}%\n"
        )

        f.write(
            f"largest group observations: "
            f"{main_count}\n"
        )

        f.write(
            f"all observations: "
            f"{valid_count}\n\n"
        )

        f.write(
            "Center\n"
        )

        f.write(
            "------\n"
        )

        f.write(
            f"RA:  "
            f"{format_ra(center_ra)}\n"
        )

        f.write(
            f"Dec: "
            f"{format_dec(center_dec)}\n\n"
        )

        f.write(
            "Angular radius around center\n"
        )

        f.write(
            "----------------------------\n"
        )

        f.write(
            f"80%: "
            f"{radii[80]:.6f} deg\n"
        )

        f.write(
            f"95%: "
            f"{radii[95]:.6f} deg\n"
        )

        f.write(
            f"99%: "
            f"{radii[99]:.6f} deg\n"
        )


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Find the largest observation "
            "region in an MPC80 file, "
            "calculate its center, and "
            "calculate its 80/95/99 percent "
            "angular radii."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Input MPC80/OBS80 file."
    )

    parser.add_argument(
        "--output",
        help="Optional text output file."
    )

    args = parser.parse_args()

    observations = []

    total_lines = 0
    ignored_lines = 0

    print(
        f"Reading: {args.input}"
    )

    with open(
        args.input,
        "r",
        encoding="utf-8-sig",
        errors="replace"
    ) as infile:

        for raw_line in infile:

            total_lines += 1

            line = raw_line.rstrip(
                "\r\n"
            )

            parsed = parse_mpc80(
                line
            )

            if parsed is None:

                ignored_lines += 1

                continue

            observations.append(
                parsed
            )

    valid_count = len(
        observations
    )

    if valid_count == 0:

        print(
            "ERROR: No valid MPC80 "
            "observations found.",
            file=sys.stderr
        )

        sys.exit(1)

    print(
        f"Valid observations: "
        f"{valid_count}"
    )

    print(
        "Finding observation groups "
        "within 1 degree..."
    )

    groups = build_groups(
        observations
    )

    group_count = len(groups)

    # 最大の連結成分
    main_group = groups[0]

    main_count = len(
        main_group
    )

    main_percentage = (
        100.0
        * main_count
        / valid_count
    )

    # ---------------------------------------------------------
    # 中心計算
    #
    # 主要領域に属する全観測を使用する。
    # 「1度以内に他の観測がない観測」の除外は行わない。
    # ---------------------------------------------------------

    center_ra, center_dec = spherical_mean(
        observations,
        main_group
    )

    # ---------------------------------------------------------
    # 主要領域内の全観測について、
    # 計算した中心からの角距離を求める。
    # ---------------------------------------------------------

    distances = []

    for i in main_group:

        ra, dec = observations[i]

        distance = angular_distance_deg(
            center_ra,
            center_dec,
            ra,
            dec
        )

        distances.append(
            distance
        )

    distances.sort()

    radii = {
        80: percentile(
            distances,
            80
        ),

        95: percentile(
            distances,
            95
        ),

        99: percentile(
            distances,
            99
        )
    }

    print()
    print(
        "Main observation region"
    )
    print(
        "-----------------------"
    )

    print(
        f"largest group/all = "
        f"{main_percentage:.4f}%"
    )

    print(
        f"largest group observations: "
        f"{main_count}"
    )

    print(
        f"all observations: "
        f"{valid_count}"
    )

    print()
    print("Center")
    print("------")

    print(
        f"RA:  "
        f"{format_ra(center_ra)}"
    )

    print(
        f"Dec: "
        f"{format_dec(center_dec)}"
    )

    print()
    print(
        "Angular radius around center"
    )
    print(
        "----------------------------"
    )

    print(
        f"80%: "
        f"{radii[80]:.6f} deg"
    )

    print(
        f"95%: "
        f"{radii[95]:.6f} deg"
    )

    print(
        f"99%: "
        f"{radii[99]:.6f} deg"
    )

    if args.output:

        write_output(
            args.output,
            args.input,
            total_lines,
            valid_count,
            ignored_lines,
            group_count,
            main_count,
            main_percentage,
            center_ra,
            center_dec,
            radii
        )

        print()
        print(
            f"Result written to: "
            f"{args.output}"
        )


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
from collections import Counter


# ============================================================
# MPC80観測行かどうかを判定
# ============================================================

def is_mpc80_line(line):

    if len(line) < 80:
        return False

    # 年
    try:
        year = int(line[15:19])

        # 月
        month = int(line[20:22])

        # 日
        day = float(line[23:32])

    except (ValueError, IndexError):

        return False

    # 基本的な日付チェック
    if year < 1900:
        return False

    if month < 1 or month > 12:
        return False

    if day < 1.0 or day >= 32.0:
        return False

    # MPC80の観測所コード
    obscode = line[77:80]

    # 空白だけなら観測行として扱わない
    if not obscode.strip():
        return False

    return True


# ============================================================
# ITFを読み込んで観測所・日付ごとにカウント
# ============================================================

def count_observations(filename, target_station):

    counts = Counter()

    total_lines = 0
    valid_mpc80 = 0
    station_lines = 0

    with open(
        filename,
        "r",
        encoding="utf-8-sig",
        errors="replace"
    ) as f:

        for line in f:

            total_lines += 1

            line = line.rstrip("\r\n")

            # MPC80でなければ無視
            if not is_mpc80_line(line):
                continue

            valid_mpc80 += 1

            # 観測所コード
            obscode = line[77:80].strip()

            # 指定観測所でなければ無視
            if obscode != target_station:
                continue

            station_lines += 1

            # 年月日
            year = int(line[15:19])
            month = int(line[20:22])
            day = int(float(line[23:32]))

            date = (
                year,
                month,
                day
            )

            counts[date] += 1

    return (
        counts,
        total_lines,
        valid_mpc80,
        station_lines
    )


# ============================================================
# main
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "MPC80形式のITFから、指定した観測所コードについて"
            "年月日ごとの観測数を集計します。"
        )
    )

    parser.add_argument(
        "-itf",
        "--itf",
        required=True,
        help="入力ITFファイル"
    )

    parser.add_argument(
        "-station",
        "--station",
        required=True,
        help="観測所コード（例: T09）"
    )

    args = parser.parse_args()

    station = args.station.strip()

    print(
        f"Reading: {args.itf}"
    )

    print(
        f"Station: {station}"
    )

    (
        counts,
        total_lines,
        valid_mpc80,
        station_lines
    ) = count_observations(
        args.itf,
        station
    )

    print()

    print(
        "Date                 Observations"
    )

    print(
        "-----------------------------------"
    )

    # 日付順に表示
    for (
        year,
        month,
        day
    ) in sorted(counts):

        print(
            f"{year:04d}-{month:02d}-{day:02d}"
            f"          "
            f"{counts[(year, month, day)]}"
        )

    print()

    print(
        f"Total input lines : {total_lines}"
    )

    print(
        f"Valid MPC80 lines : {valid_mpc80}"
    )

    print(
        f"Station {station} : {station_lines}"
    )

    print(
        f"Number of dates   : {len(counts)}"
    )


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse


# ============================================================
# MPC80形式の観測行かどうかを確認
# ============================================================

def is_mpc80_line(line):

    if len(line) < 80:
        return False

    try:
        # 年
        year = int(line[15:19])

        # 月
        month = int(line[20:22])

        # 日
        day = float(line[23:32])

        # RA
        hour = int(line[32:34])
        minute = int(line[35:37])
        second = float(line[38:44])

        # Dec
        sign = line[44]

        if sign not in ("+", "-"):
            return False

        deg = int(line[45:47])
        decmin = int(line[48:50])
        decsec = float(line[51:56])

        # 観測所コード
        obscode = line[77:80].strip()

    except (ValueError, IndexError):

        return False

    # 基本的な値のチェック
    if year < 1900:
        return False

    if month < 1 or month > 12:
        return False

    if day < 1.0 or day >= 32.0:
        return False

    if hour < 0 or hour > 23:
        return False

    if minute < 0 or minute > 59:
        return False

    if second < 0 or second >= 60:
        return False

    if deg < 0 or deg > 90:
        return False

    if decmin < 0 or decmin > 59:
        return False

    if decsec < 0 or decsec >= 60:
        return False

    if not obscode:
        return False

    return True


# ============================================================
# 等級欄が空白かどうか
#
# MPC80:
# magnitude = columns 66-70
# Pythonでは line[65:70]
# ============================================================

def has_magnitude(line):

    magnitude_field = line[65:70]

    # 5文字すべて空白なら等級なし
    if magnitude_field.strip() == "":
        return False

    # 念のため、数値として読めるか確認
    try:
        float(magnitude_field)

    except ValueError:
        return False

    return True


# ============================================================
# メイン処理
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "MPC80形式ITFから、"
            "等級値が空白の観測行を除外します。"
        )
    )

    parser.add_argument(
        "-input",
        "-i",
        required=True,
        help="入力ITFファイル"
    )

    parser.add_argument(
        "-output",
        "-o",
        required=True,
        help="出力ITFファイル"
    )

    args = parser.parse_args()

    total_lines = 0
    valid_lines = 0
    kept_lines = 0
    removed_nomag = 0
    ignored_lines = 0

    print(
        f"Input : {args.input}"
    )

    print(
        f"Output: {args.output}"
    )

    with open(
        args.input,
        "r",
        encoding="utf-8-sig",
        errors="replace"
    ) as infile, open(
        args.output,
        "w",
        encoding="utf-8",
        newline=""
    ) as outfile:

        for line in infile:

            total_lines += 1

            # 改行だけ除去し、観測行自体は変更しない
            content = line.rstrip("\r\n")

            # MPC80でない行は無視
            if not is_mpc80_line(content):

                ignored_lines += 1
                continue

            valid_lines += 1

            # 等級なしなら除外
            if not has_magnitude(content):

                removed_nomag += 1
                continue

            # 等級ありならそのまま出力
            outfile.write(
                content + "\n"
            )

            kept_lines += 1

    print()
    print(
        "Processing finished."
    )

    print(
        f"Total input lines       : {total_lines}"
    )

    print(
        f"Valid MPC80 lines       : {valid_lines}"
    )

    print(
        f"Removed (no magnitude)  : {removed_nomag}"
    )

    print(
        f"Ignored invalid lines   : {ignored_lines}"
    )

    print(
        f"Output observations     : {kept_lines}"
    )


if __name__ == "__main__":
    main()
#!/usr/bin/env python3

import sys
from pathlib import Path


def split_file(input_file, split_count):
    input_path = Path(input_file)

    if not input_path.exists():
        print(f"エラー: ファイルが見つかりません: {input_file}")
        sys.exit(1)

    if split_count < 1:
        print("エラー: 分割数は1以上にしてください。")
        sys.exit(1)

    # ファイルを読み込む
    with open(input_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if not lines:
        print("エラー: 入力ファイルが空です。")
        sys.exit(1)

    # 1行目をヘッダーとする
    header = lines[0]
    data_lines = lines[1:]

    total_data = len(data_lines)

    if total_data == 0:
        print("エラー: ヘッダー以外のデータがありません。")
        sys.exit(1)

    # 分割数がデータ行数を超える場合
    if split_count > total_data:
        print(
            f"警告: 分割数({split_count})がデータ行数({total_data})より多いため、"
            f"分割数を{total_data}に変更します。"
        )
        split_count = total_data

    # 基本の行数と余り
    base_size = total_data // split_count
    remainder = total_data % split_count

    stem = input_path.stem
    suffix = input_path.suffix

    start = 0

    for i in range(split_count):
        # 余りがある場合、前方のファイルに1行ずつ追加
        current_size = base_size + (1 if i < remainder else 0)
        end = start + current_size

        output_name = f"{stem}_part{i + 1:02d}{suffix}"
        output_path = input_path.parent / output_name

        with open(output_path, "w", encoding="utf-8", newline="") as f:
            # ヘッダーを各ファイルに書き込む
            f.write(header)

            # データを書き込む
            f.writelines(data_lines[start:end])

        print(
            f"{output_name}: "
            f"データ {current_size} 行"
        )

        start = end

    print()
    print(f"入力ファイル: {input_path}")
    print(f"ヘッダー: 1行")
    print(f"データ行数: {total_data}")
    print(f"分割数: {split_count}")
    print("分割完了")


def main():
    if len(sys.argv) != 3:
        print(
            "使用方法:\n"
            "  python split_heliohypo.py <入力ファイル> <分割数>\n\n"
            "例:\n"
            "  python split_heliohypo.py heliohypo_mb05.txt 4"
        )
        sys.exit(1)

    input_file = sys.argv[1]

    try:
        split_count = int(sys.argv[2])
    except ValueError:
        print("エラー: 分割数は整数で指定してください。")
        sys.exit(1)

    split_file(input_file, split_count)


if __name__ == "__main__":
    main()
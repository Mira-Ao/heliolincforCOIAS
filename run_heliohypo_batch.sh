#!/bin/bash

# HelioLinc本体
HELIO="../src/heliolinc"

# 仮説ファイルの基本名
BASE="heliohypo_mb05"

# 分割数
COUNT=200

# 共通入力ファイル
IMGS="outimgs.txt"
PAIRDETS="pairdets.csv"
TRACKLETS="tracklets.csv"
TRK2DET="trk2det.csv"
OBSPOS="Earth1day200030.csv"

# 開始時刻
echo "========================================"
echo "HelioLinc batch processing started"
echo "Start: $(date)"
echo "========================================"

for ((i=1; i<=COUNT; i++))
do
    PART=$(printf "%02d" "$i")

    HYPO="${BASE}_part${PART}.txt"
    SUMFILE="sumfile_part${PART}.csv"
    CLUST2DET="clust2detfile_part${PART}.csv"

    echo ""
    echo "========================================"
    echo "Processing part ${i}/${COUNT}"
    echo "Hypothesis : ${HYPO}"
    echo "Sum file   : ${SUMFILE}"
    echo "Clust2det  : ${CLUST2DET}"
    echo "Start      : $(date)"
    echo "========================================"

    # 仮説ファイルの存在確認
    if [ ! -f "$HYPO" ]; then
        echo "ERROR: ${HYPO} が見つかりません。"
        echo "処理を中止します。"
        exit 1
    fi

    # HelioLinc実行
    "$HELIO" \
        -imgs "$IMGS" \
        -pairdets "$PAIRDETS" \
        -tracklets "$TRACKLETS" \
        -trk2det "$TRK2DET" \
        -obspos "$OBSPOS" \
        -heliodist "$HYPO" \
        -clustrad 2e5 \
        -mintimespan 1 \
        -outsum "$SUMFILE" \
        -verbose -1 \
        -clust2det "$CLUST2DET"

    STATUS=$?

    echo ""
    echo "Part ${i}/${COUNT} finished."
    echo "End: $(date)"
    echo "Exit status: ${STATUS}"

    # エラーが発生したら停止
    if [ $STATUS -ne 0 ]; then
        echo ""
        echo "ERROR: HelioLinc が異常終了しました。"
        echo "Part ${i} で処理を停止します。"
        exit $STATUS
    fi
done

echo ""
echo "========================================"
echo "All ${COUNT} parts completed successfully."
echo "End: $(date)"
echo "========================================"
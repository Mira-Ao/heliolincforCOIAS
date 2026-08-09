extract_cluster_itf.py

heliolinxで最後にlink_purefyで出力されたsumfileとclust2detfileと、pairdetと入力観測を参照して、クラスターごとに観測を元の名前で復元し、位置のRMS（arcsec）を添えてまとめてくれます。

python3 extract_cluster_itf.py \
    --clust2det LPclust2detfile.csv \
    --sum LPsumfile.csv \
    --pairdet pairdets.csv \
    --itf your_itf.txt \
    --output finalout_itfMPC80.txt

で

    Cluster 1
    astromRMS   : 0.0829
    Observations: 13

     H378680*4C2015 03 20.41605 12 08 21.01 +00 05 00.1          23.4 i1     T09
     H378680 4C2015 03 20.46072 12 08 19.66 +00 05 06.8          23.5 i1     T09
     H378680 4C2015 03 20.49692 12 08 18.58 +00 05 12.1          23.4 i1     T09
     H378680 4C2015 03 20.53554 12 08 17.41 +00 05 17.9          23.6 i1     T09
     H381820*4C2015 03 25.47205 12 05 52.34 +00 17 31.0          24.1 g1     T09
     H381820 4C2015 03 25.48492 12 05 51.95 +00 17 33.0          23.9 g1     T09
     H381820 4C2015 03 25.51107 12 05 51.16 +00 17 36.8          24.2 g1     T09
     H381820 4C2015 03 25.52811 12 05 50.65 +00 17 39.3          24.1 g1     T09
     H381820 4C2015 03 25.55400 12 05 49.88 +00 17 43.1          24.2 g1     T09
     H381820 4C2015 03 25.55615 12 05 49.81 +00 17 43.5          24.8 g1     T09
     H458971*4C2015 03 18.47125 12 09 17.92 +00 00 11.0          24.0 r1     T09
     H458971 4C2015 03 18.50552 12 09 16.89 +00 00 16.2          24.0 r1     T09
     H458971 4C2015 03 18.57964 12 09 14.67 +00 00 27.1          23.9 r1     T09

みたいな感じ
MPC提出用jsonも出します。



Singleton_filter.py


上の出力ファイルからシングルトン（1観測/1夜）を含むリンクを削除します。

 python3 Singleton_filter.py \
  --itf finalout_itfMPC80.txt \
  --linkage finalout_itfMPC80_linkage.json \
  --output finalout_itfMPC80_filtered.txt \
  --output-linkage finalout_itfMPC80_filtered_linkage.json



Earth1day200030.csv

heliolincで使える2000年から2030年までの地球位置ファイルです。




ITFsearch.py

　python3 ITFsearch.py --itf itf.txt --output searchedITF.txt --startdate 2015-03-18 --enddate 2015-03-25 --RA "12 00 00" --Dec "-12 05 00" --deg 20 --station T09

のようにして、任意のITFファイル（--itf）から出力ファイル（--output）に、任意の日付の期間（--startdateから--enddate）の、特定の座標位置（--RA --Dec）からX度以内（--deg）の特定の観測所（--station）の観測を書き出します。使わない引数は入力しなければOKで、たとえば--stationを飛ばせば条件に合う全世界の観測所の観測が含まれます。なおheliolincでエラーになる、位置情報付きの観測（C51 WISEなどの宇宙望遠鏡や移動観測地）は除外します。

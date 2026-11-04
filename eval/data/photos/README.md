# Benchmark photos

Eight street photos from Taiwan, all released into the public domain by their authors under
[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) on Wikimedia Commons. CC0 needs no
attribution, but the authors and sources are listed here anyway, so every image can be traced.

Changes made for this repository: downloaded as Commons thumbnails, resized so the longer side is
1400 px, re-saved as JPEG (quality 80) with the metadata removed. Nothing else was edited.

| File | Author | Taken | Lines graded | Source |
|---|---|---|---:|---|
| taipei-street-signs.jpg | Brian Hioe | 2022-01-23 | 12 | [Taipei street signs.jpg](https://commons.wikimedia.org/wiki/File:Taipei_street_signs.jpg) |
| aan-migao-night.jpg | Shouji Hasegawa | 2018-02-17 | 10 | [阿岸米糕20180217.jpg](https://commons.wikimedia.org/wiki/File:%E9%98%BF%E5%B2%B8%E7%B1%B3%E7%B3%9520180217.jpg) |
| night-road-signs.jpg | Ounfs Robmmy 238 | 2024-03-10 | 10 | [TW 台灣 Taiwan 台北 Taipei 松山 SongShan shop 蝦鮮味料理 restaurant sign night March 2024 R12S.jpg](https://commons.wikimedia.org/wiki/File:TW_%E5%8F%B0%E7%81%A3_Taiwan_%E5%8F%B0%E5%8C%97_Taipei_%E6%9D%BE%E5%B1%B1_SongShan_shop_%E8%9D%A6%E9%AE%AE%E5%91%B3%E6%96%99%E7%90%86_restaurant_sign_night_March_2024_R12S.jpg) |
| sheng-chun-shop.jpg | 玄史生 | 2015-02-01 | 12 | [Sheng Chun Shop 20150201.jpg](https://commons.wikimedia.org/wiki/File:Sheng_Chun_Shop_20150201.jpg) |
| noodle-shop-21.jpg | 玄史生 | 2016-01-30 | 17 | [21 Worker House Hand-made Chilled Noodles Jiuquan Store 20160130.jpg](https://commons.wikimedia.org/wiki/File:21_Worker_House_Hand-made_Chilled_Noodles_Jiuquan_Store_20160130.jpg) |
| guixian-village-sign.jpg | 玄史生 | 2017-12-29 | 2 | [Sign of Guixian Village, Taishan District, New Taipei 20171229.jpg](https://commons.wikimedia.org/wiki/File:Sign_of_Guixian_Village,_Taishan_District,_New_Taipei_20171229.jpg) |
| street-name-signs.jpg | 玄史生 | 2015-02-17 | 2 | [Former Fujin Street and Sanmin Road Name Signs in Fumin Ecology Park 20150217.jpg](https://commons.wikimedia.org/wiki/File:Former_Fujin_Street_and_Sanmin_Road_Name_Signs_in_Fumin_Ecology_Park_20150217.jpg) |
| teppanyaki-sign.jpg | 玄史生 | 2016-09-29 | 5 | [Female Rider Watching Broken Teppanyaki Restaurant Sign at Xindong Street, Taipei 20160929.jpg](https://commons.wikimedia.org/wiki/File:Female_Rider_Watching_Broken_Teppanyaki_Restaurant_Sign_at_Xindong_Street,_Taipei_20160929.jpg) |

Downloaded on 2026-11-04.

## Labels

[`labels.json`](labels.json) lists, for every photo, the text lines that are clear enough to grade:
the text as written on the sign and an outline around it (`box` or `polygon`, in pixels of these
files). Lines marked `###` are text that is too small, cut off or ambiguous to grade; anything an
engine reads inside them is ignored.

How they were made: the outlines started from PaddleOCR's detections and were checked against the
photo, widened a little, and replaced by hand-measured boxes where lines sit close together or the
detector missed them. The text was typed from the photo, not copied from any engine, and checked on
zoomed crops. Licence plates and product logos were not labelled.

To see the labels drawn on the photos: `python eval/draw_labels.py photos /tmp/labels`.

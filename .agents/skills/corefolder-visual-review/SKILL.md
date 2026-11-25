---
name: corefolder-visual-review
description: Compare NumberTales Corefolder VRM renders with official DB artwork and individual tail atlases. Use when refining likeness, silhouette, facial proportions, rear layering, and Unity rendering after a sculpt change.
---

# コアフォルダの造形照合

公式DBの番号・形態・尻尾房数を照合し、同じキャラの通常表情の全身絵、表情違い、尻尾アトラスを開く。人型の衣装と装飾は形態の適用条件を原文で確認する。

1. 変更前の実VRMを保存し、プロジェクトのPC用URP・MToon・正投影で、正面・側面・背面と原画に近い斜視を撮る。角度選びには顔の向き、左右の耳の重なり、胸の番号の位置を用いる。選んだ角度は改稿後にも固定する。
2. 全身と、独立した尾メッシュだけを正対させた背面を分けて照合する。公式全身絵と尾のアトラスのそれぞれに、対応するレンダーを渡す。
3. リポジトリ直下で `python 100BeautiesLab-CharacterNative/NumberTales/Corefolder-Training/compare_corefolder_art.py 公式.png 変更前.png 変更後.png 比較.png` を実行する。画像の縦横比を保って枠を合わせる。出力図の青は原画だけにある面、橙はモデルだけにある面。IoUと上下8帯の占有率は差の位置を探すために読む。
4. 顔を拡大し、耳内外、目の開き・虹彩・瞳孔、口角、房の付け根と顔／首の継ぎ目を比較する。装飾の番号の左右・欠け・鏡文字、側面の貫通、背面で尾の本数と重なりが読めるか確かめる。線が合っても奥行きは別の角度で見る。
5. 問題を実際のメッシュ、UV、材質またはウェイトに直して再撮影する。規範6体とも同じ世界縮尺の三面で並べる。表情はUnityの変形済みメッシュをベイクして撮影し、揺れは運動中と停止後の毛先・実頂点で確かめる。版のハッシュ、直した差、原画で決められない奥行きを制作記録に残す。

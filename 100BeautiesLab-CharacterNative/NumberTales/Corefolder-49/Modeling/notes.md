# コアフォルダ #49 ヨチカ

`Corefolder-49.blend` は編集用、`Corefolder-49.vrm` は VRM 0.x の書き出し。Blender 5.3.0 と VRM Add-on 4.10.5 を使用した。

## デザインと出典

- 公式 CreationsDB の `data/Works_NumberTales/DataBases/db_Primary.json` の Num 49 と、`Images/DB_Primary/corefolder/49/emstk_corefolderNTS-49-{1,2}.png` を参照した。空色の毛・白腹・明るい青のミディアムヘア、両側の狐耳、紺色の虹彩・紫の縦瞳、頬の短線、横長の口を立体化した。左胸の「49」は `attr/numberMark/attr_numberMarkNTS-49.png` の透過原図を白い前身に焼き込んだ。制服などは DB のヒューマノイド形態に属する。
- 配色は毛の主色 `#6AA6D7`、淡い毛先と耳内側 `#9BC1E6`、虹彩 `#405AB9` と `#4378C3`、瞳の差し色 `#BD8AE6`。やや下がった上瞼・長短のある前髪・外向きの頬毛・後ろへ重なる襟足を形状にした。正面寄りの設定画に見えない後頭部の厚みと喉の奥行きは立体化時の補間。
- `attr/tailsUnit/attr_tailsUnitNTS-49.png` と DB の上4本・下5本を照合した。上は左右に2房ずつ、各房の淡色の端面を実際に二分して長短の毛先を作った。下は手前へ回る左右、外側左右、中央下の5房。背面の根元から前へ回り込む距離は正面絵と背面アトラスに合わせて定めた。毛先の分岐は同じ房の中で動く。
- 公式デザインカタログ `catalog/chr-dsgn_catalogNTS-49.png` とイラスト `arts/corefolders/2023/art_imgNTS-49-corefolder.png` でも照合した。2023年の絵には白い喉毛の線が出ている。顔と胸の接続はカタログのコアフォルダ図・上記の表情立ち絵2枚に合わせた。
- 共通素体は `Basis/Corefolder/VRCModel_CoreFloder-Base.blend` 由来。#4の顔・UV・骨格・表情を備えた #49 編集用スターターを使い、胴体の下部を広げ、顔の全モーフに同じ眼裂・唇の変形を適用した。顔アトラスの頬・虹彩・瞳・ハイライト・口縁を #49 用に描き直した。#22 の本体・顔 MToon 設定を起点に、白い毛の陰影と青い毛束の輪郭幅・色を調整した。

## 編集と再生成

- 胴と顔、髪の房、耳の外殻・裏地・内毛、9本の尾は Blender で個別に編集できる。4枚の PNG は blend に同梱した UV 画像と同じ内容。尾9系統と左右の頬毛2系統にはウェイトと VRM SpringBone を設定した。番号と頬線は表面に追従する。
- `paint_49.py <CreationsDB のパス>` は Pillow と NumPy で塗りを再生成する。編集済みの PNG を使う場合はこの工程を省ける。
- Blender バックグラウンドで `model_49.py -- --starter <Corefolder-49-Starter.blend> --out <別の出力先>` を実行する。スターターを作り直す場合は隣接する `Corefolder-Training/create_corefolder_base.py` に `--number 49 --style 22 --material CoreFolder022.001 --face-style 22 --face-material CoreFolder022-2.001` と DB・出力先を指定する。
- 書き出した VRM を再読込し、正面・斜め・側面・背面で番号の向き、喉の閉じ、白腹の幅、上房の分岐、下房の前への巻きを照合した。表情13種は元の VRM のバインドを継承する。

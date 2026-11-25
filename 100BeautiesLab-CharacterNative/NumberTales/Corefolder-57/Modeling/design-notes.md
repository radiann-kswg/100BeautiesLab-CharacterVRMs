# #57 イズナ／Fivens のコアフォルダ造形

`Corefolder-57.blend` が編集用、`Corefolder-57.vrm` がUnity用のVRM 0.xだよ。Blender 5.3.0とVRM Add-on 4.10.5を使用。VRMのSHA-256は `ec4fb23f93c905cdb645573e2bb78c7365cad8676f683aff93fe084fb5422ed6`。

## 原作の特徴と立体の規範

| 資料 | モデルへの反映 |
| --- | --- |
| 創作DB `Works_NumberTales/DataBases/db_Primary.json` の57番、`Images/DB_Primary/corefolder/57/emstk_corefolderNTS-57-1.png` と2枚目 | 暖かい黄の毛色、白腹、高い狐耳、中央の長い前髪、右のサイドポニー、黄緑の虹彩と青い瞳孔、右肩の腕章。 |
| `catalog/chr-dsgn_catalogNTS-57.png` の Rough Design | 立ち絵1で隠れた側の瞳孔と光の向きを、コアフォルダの両眼が開いた図で確認した。 |
| #93の立ち絵1と同番号の実VRM | 面積のある中央の房、縦長の瞳孔と細い外周、淡い頬の広がりを照合した。中央と外側の太い3房を閉じた曲面にし、左右別のUVへ黄緑の二段塗りと青い芯を描いた。#4の右上の小さい光、#16のぼかし頬を参照し、固有の斜線を薄く重ねた。 |
| #25の立ち絵2と同番号の実VRM | 頬の横を通る側房の厚みと位置を確認。頬毛は基準顔に根を埋め、外側で白い先端を出した。 |
| `attr/numberMark/attr_numberMarkNTS-57.png`、`attr/tailsUnit/attr_tailsUnitNTS-57.png` | 腕章への「57」の印刷と、七尾の模様・本数を確認。尾の共通実装は `atlas_tail_sculpt.py` と `native_tail_profiles.py`、固有データは `Tails-57.json` と `Tails-57.png`。 |

耳は後面・黄白の縁・内側の浅いくぼみをひと続きの断面で形成した。ポニーは結び目から丸い膨らみ、細い毛先へ向かう14角断面の曲線で、両耳際の髪と別々に揺れる。腕章の白地、2本の線、数字を肩に巻き、上端に留め具を置いた。公式の主要色は `#FFEE62`。毛皮・黄色い髪・耳はプロジェクトのリニアURPに合わせてベースと陰影の係数を0.77倍にした。後頭部、耳の厚みとポニー根元の奥行きは、2方向の絵と規範から決めた立体上の解釈だよ。

## 規範の体形とリグ

`Corefolder-57-Refined.blend` から開始し、素体 `Basis/Corefolder/VRCModel_CoreFloder-Base.blend` の胴を読み込み直した。中間稿の胴は幅1,133.7 mm、高さ782.9 mm。現稿は幅853.9 mm、高さ711.7 mm。編集用 `.blend` の中立スキンをワールドZで切ると、床から100/250/370/510/630 mmの全断面で規範 #93 の胴の幅との差は0.0 mm、奥行差は0.1–0.2 mm（0.1 mm丸め）。370 mm位置の幅・奥行きは853.8・872.7 mm。腕章と留め具をこの肩に合わせた。

`canonical_face.py` で規範 #4 実VRMの頭・首・両眼・眼窩・瞼・中立顔・15モーフを対応させ、共通工程で #93 の唇・口腔の発音リグを取り込んだ。七尾と3房に独立したSpring Boneがある。点群・画像モデルの追加学習は0回。

## 実VRMの比較

`Fit-Fivens.png` は公式絵2・旧Refined・現稿を全高で揃えた比較だよ。実VRMをBlenderに再読込し、中立姿勢を方位19度・仰角2度で撮影。幅／高さは公式1.022、旧0.983、現稿0.928。腕章の黄緑の重心は上から51.89%、53.31%、56.45%。全身のマスクIoUは旧0.820、現稿0.784。原画では体を腕章側に傾けている。現稿は規範の中立体形を保っており、上半身の正面幅、ポニーの見える幅、腕章の高さに差が残る。六体と同条件のUnity撮影・動作検証は `Corefolder-Training/production-review/` にあるよ。

`Eye-Fit.png` は画面左・画面右の目を原画、前稿、現稿、両眼骨を同方向へ8度回した現稿で比較した。白い反射はUVセルの左端から67.8%と71.7%。正面720 pxのBlender撮影で青い瞳孔が両方とも画面右へ2.41 pxと2.22 px移動した。

## 再生成

```powershell
$blender = 'C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe'
$builder = '100BeautiesLab-CharacterNative/NumberTales/Corefolder-Training/upgrade_refined_character.py'
& $blender --background --offline-mode --disable-autoexec --python-exit-code 1 --python $builder -- --number 57 --out '.cache/fivens-rebuild'
```

画像を作り直す場合はPillowとNumPyがあるPythonで `textures_57.py` を実行する。個別形状の入口は `design_57.py` の `revise(arm, collection)` だよ。

# #57 イズナ／Fivens のコアフォルダ造形

`Corefolder-57-Refined.blend` の骨格と表情キーを起点に、`design_57.py` の `revise(arm, collection)` が胴、顔まわり、髪、両耳、キャラクター自身の右腕章を組み直すよ。尾の形は共通工程の `atlas_tail_sculpt.py` とこのフォルダの `Tails-57.json`・`Tails-57.png` に対応している。

## 絵と設定の使い分け

- 創作 DB の `Works_NumberTales/DataBases/db_Primary.json` の57番と、`Images/DB_Primary/corefolder/57/emstk_corefolderNTS-57-{1,2}.png` を参照。1枚目は正面寄りで片目を閉じて笑い、2枚目は横を向き、両目を細く開いている。ニュートラルの造形を決める際には2枚とも見た。
- 前髪は左右の目を基準に1枚目から黄色の画素を抽出し、中央で下がる幅広い房と左右の垂れた輪郭を前頭部の曲面へ移した。後頭部は閉じた立体。右サイドポニーは結び目、膨らみ、身体の側面に下がる細い先端を持つ独立したメッシュ。左右の耳際の髪と別々のばねで動く。
- 背の高い狐耳は黄の外面、黄白の縁、淡黄の内側を前後で作り分けた。片目を開いた絵で読める青い瞳孔と、もう1枚で分かる黄緑色の虹彩の上下二色を、顔の表情 UV へ描いた。目尻・まぶた・瞬きの頂点対応を継承。
- 胴には丸い白腹と細い金色の境界を一枚の UV で配置した。腕章は公式 `attr/numberMark/attr_numberMarkNTS-57.png` の「57」を使用。白地・二本の黄緑の線・印刷・上の留め具が胴の曲面に沿う。右肩の傾きは本体に投影して決めた。
- 公式1枚目の髪や主要な毛色の画素は暖黄 `#FFEE62`。プロジェクトのリニア URP による白飛びを抑えるため、毛皮・髪・耳の MToon のベース係数と陰影係数を線形 0.77 倍にしている。

原画で隠れた後頭部の奥行き、耳の厚み、ポニーの付け根は、2方向の絵と規範モデルをもとに決めた立体上の解釈だよ。新規学習は行わず、形状・テクスチャ・スキンウェイトを編集した。

## 再生成

`Fivens-*.png` は同梱している。画像を作り直す場合は Pillow、NumPy、SciPy を入れた Python で `textures_57.py` を実行する。リポジトリ直下から次のコマンドで、顔と髪、尾、表情、Spring Bone を備えたモデルを指定先に出力できる。

```powershell
$blender = 'C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe'
$builder = '100BeautiesLab-CharacterNative/NumberTales/Corefolder-Training/upgrade_refined_character.py'
& $blender --background --offline-mode --disable-autoexec --python-exit-code 1 --python $builder -- --number 57 --out '.cache/fivens-rebuild'
```

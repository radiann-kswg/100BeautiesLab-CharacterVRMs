# #57 イズナ / Fivens のコアフォルダ制作記録

編集用は `Corefolder-57.blend`、Unity用は `Corefolder-57.vrm` だよ。Blender 5.3.0 と VRM Add-on 4.10.5 で制作したVRM 0.xのSHA-256は `f5e81e968e009677f5b39e25616673c40f2176b98fcf22a984e7c80229e19f7c`。

## 規範の頭・胴と衣装

衣装の下には基準VRM #4の左右対称の胴、眼窩、頬と顎、首・頭・両眼の骨がある。共通 `VRCModel_CoreFloder-Base.blend` の裸胴を取り込み、`torso_profile.py` が #4実VRMの1,078点に合わせる。出力された胴材質部分の最大幅は853.9 mm、前後は872.9 mm、高さは711.6 mm。顔の開口34点を #4・#25・#93 の後頭部の外形から再構成した共通頭蓋へつないだ。VRMのレンダラーは `Face, Body, Hair, Tail, Outfit`。Outfitを外すと固有の衣装が外れ、Hairも外すとBodyに属する後頭部とFaceの表情面を確認できる。

固有の毛色は胴のスキンと同じUV面に置いた。`Waist-Fit.png` に #16・#93 と旧稿・現稿の実VRMから取り出した胴テクスチャを実寸の正投影で並べた。中央の白が占める全幅の割合は床上100 mmで55.1%／27.1%／59.4%／45.4%、370 mmで66.2%／51.9%／49.3%／62.4%。左から #16、#93、旧稿、現稿。白腹を腰でふくらませ、裾に向けて色毛が回り込む曲線にした。腰の旧稿は白腹改稿前（SHA先頭 `ec4fb23f93c9`）、後述する頭の旧稿は白腹改稿後・髪の組み直し前（`2ad72938fec5`）。画像は無照明の色と形を測るためのもので、Unityの照明での見え方は共通 `Corefolder-Training/production-review/` の三面図に記録した。

右肩に巻く腕章の白地・黄緑の二本線・数字・留め具をOutfitに分けた。肩の曲面の頂点ウェイトを補間して追従させ、中立姿勢で腕章310点を調べた最小の水平半径方向の隙間は4.76 mm。首元の見え方は共通胴と顎で決まり、独立した長い黒の顎線は外した。

## 一次資料と造形

創作DB `Works_NumberTales/DataBases/db_Primary.json` の57番、コアフォルダ立ち絵1・2、`catalog/chr-dsgn_catalogNTS-57.png` のRough Designを参照。暖色の黄、白腹、高い狐耳、中央の長い前髪、右のポニー、黄緑の虹彩と青い瞳孔、右肩の腕章が特徴だよ。`attr/numberMark/attr_numberMarkNTS-57.png` を腕章に印刷。七尾のデザインは `attr/tailsUnit/attr_tailsUnitNTS-57.png` を参照し、曲面に対応する `Tails-57.json` と `Tails-57.png` を使った。黄の原色は `#FFEE62`、プロジェクトのリニアURP向けに毛皮のベースと陰影を0.77倍にした。

#93の立ち絵1と実VRMで中央房と目の縦長の芯、#25の立ち絵2と実VRMで側房の張りを比較。中央の長い一房、斜めの分け目、長さの異なる左右の房を頭頂から続く面にした。左右の耳は根元に幅と前後の厚みのある閉じた耳殻にして、内側に浅いくぼみを置いた。両脇の房は同じ曲面の末端を頭のウェイトから段階的に切り替えて揺らす。ポニーは14角の断面を外へふくらませ、毛先へ細くした。両側とポニーの3房・七尾が独立して揺れる。眼は左右別UV、#4の反射と#16の頬のぼかしを参考にした。中立顔は#4、内唇と発音形は#93の実モーフを使った。

## 実VRMの確認

全体は24,260三角形、画像7枚を内蔵。`Head-Fit.png` に旧稿・現稿のMToonと単色クレイ、規範 #93 のクレイを同じ角度・実寸で収めた。正面で見える別部品間の交線は1,501.7 mmから261.1 mmへ、同じ接続面内の交線は244.7 mmから0.0 mmへ変わった。0°、−30°、＋30°、−90°、＋90°、180°の順に別部品間の残りは261.14、259.80、178.74、173.04、73.04、0.00 mm。中立の可視交差の測定条件と衣装の隙間は `Head-Fit.json`、白腹の各高さの実測値は `Waist-Fit.json` にある。毛と白い頬の付け根、まぶたと肌の境界には規範と同様に接続が残っている。

`Fit-Fivens.png` に立ち絵2、旧Refined、現稿を同じ全高で並べた。実VRMの中立を方位19度・仰角2度で撮影した幅／高さは公式1.022、旧0.983、現稿0.933。腕章の黄緑の重心は上からそれぞれ51.89%、53.31%、56.21%。全身のマスクIoUは旧0.820、現稿0.780。原画で体を傾けているぶん、腕章の高さやポニーの見える幅には中立姿勢との差がある。

`Eye-Fit.png` は左右の目を原画、以前の左右反転版、現稿、両眼骨を8度回した現稿で並べた。UVセル左から見た白い光の重心は画面左・右それぞれ67.8%、71.7%。Blenderに再読込した実VRMを正面720 pxで撮影すると、青い部分の重心は画面右に2.41 px、2.22 px移動した。点群と画像モデルの追加訓練は各0回。Unityの共通写真とPlay Modeの動作記録は `Corefolder-Training/production-review/` にあるよ。

## 再生成

```powershell
$blender = 'C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe'
$builder = '100BeautiesLab-CharacterNative/NumberTales/Corefolder-Training/upgrade_refined_character.py'
& $blender --background --offline-mode --disable-autoexec --python-exit-code 1 --python $builder -- --number 57 --out '.cache/fivens-rebuild'
```

画像を作り直す場合はPillowとNumPyがあるPythonで `textures_57.py` を実行する。個別形状の入口は `design_57.py` の `revise(arm, collection)` だよ。

# #6 ムイ / Sics のコアフォルダ制作記録

編集用は `Corefolder-6.blend`、Unity用は `Corefolder-6.vrm` だよ。Blender 5.3.0 と VRM Add-on 4.10.5 で制作したVRM 0.xのSHA-256は `2f4f9a0d244ca272c4bcc85fb7b83b7a393a1de324112c99c2391c9334a7e161`。

## 規範の頭・胴と衣装

衣装の下には基準VRM #4の左右対称の胴、眼窩、頬と顎、首・頭・両眼の骨がある。共通 `VRCModel_CoreFloder-Base.blend` の裸胴を取り込み、`torso_profile.py` が #4実VRMの1,078点に合わせる。出力された胴材質部分の最大幅は853.9 mm、前後は872.9 mm、高さは711.6 mm。顔の開口34点を #4・#25・#93 の後頭部の外形から再構成した共通頭蓋へつないだ。VRMのレンダラーは `Face, Body, Hair, Tail, Outfit`。Outfitを外すと固有の衣装が外れ、Hairも外すとBodyに属する後頭部とFaceの表情面を確認できる。

固有の毛色は胴のスキンと同じUV面に置いた。`Waist-Fit.png` に #16・#93 と旧稿・現稿の実VRMから取り出した胴テクスチャを実寸の正投影で並べた。中央の白が占める全幅の割合は床上100 mmで55.1%／27.1%／66.2%／53.7%、370 mmで66.2%／51.9%／56.3%／66.9%。左から #16、#93、旧稿、現稿。白腹を腰でふくらませ、裾に向けて色毛が回り込む曲線にした。腰の旧稿は白腹改稿前（SHA先頭 `6b752c8eec71`）、後述する頭の旧稿は白腹改稿後・髪の組み直し前（`5d264ad3792c`）。画像は無照明の色と形を測るためのもので、Unityの照明での見え方は共通 `Corefolder-Training/production-review/` の三面図に記録した。

青い襟と6の文字、六角の花ブローチは胴に重ねる独立衣装。襟の裏にも肩に沿う断面を設け、編集データの中立姿勢で頂点と三角形中心を測った。衣装の高さと同じ水平面での最小隙間は襟2.80 mm（2,142点）、ブローチ3.50 mm（71点）。布と縫い目には胴の近接三角形のスキンを補間し、ブローチ全体は取付点のウェイトで保形する。

## 一次資料と造形

創作DB `Works_NumberTales/DataBases/db_Primary.json` の6番と `Images/DB_Primary/corefolder/6/emstk_corefolderNTS-6-1.png` ほか2点を参照。桃の毛、白腹と尖った白頬、桃色の外耳と薄色の内耳、青襟、六角形の花ブローチ、ラベンダーから青へ移る星の瞳が特徴だよ。番号と毛先の境界には `attr/numberMark/attr_numberMarkNTS-6.png` と `attr/tailsUnit/attr_tailsUnitNTS-6.png` を用いた。主色 `#FF76A2`、毛先 `#FFCEED`、襟 `#6AA6D7`。

#16の立ち絵2と実VRMの大きい前房・側髪を比較し、前髪の3つの細い先と両脇の房を頭頂から襟足まで続く表面にした。耳の内側のくぼみ、外耳と髪の根を面で接合。両側の房は頭頂側のウェイトを減衰させて、それぞれのSpring Boneにつないだ。白頬は割れた先まで対応する表裏を張り、襟に沿う面へ厚みを持たせた。#22の立ち絵2と実VRM、#4と#16の顔を参考に、左右別UVの虹彩、星と右上の光、淡く広がる頬色を描いた。

六尾は共通素体にある194頂点・224面・15断面の尾を六つの中心線へ沿わせた。根元・膨らみ・切っ先の前後差を #16・#93の実尾と比較。#93の揺れ設定を参照し、尾の剛性は0.8、側髪は0.96、抗力0.4、重力0。尾6本、側髪2本の独立Springがある。中立顔の基準は#4で、唇と口腔の発音形には#16の実モーフを利用した。

## 実VRMの確認

全体は14,568三角形、画像7枚を内蔵。`Head-Fit.png` に旧稿・現稿のMToonと単色クレイ、規範 #16 のクレイを同じ角度・実寸で収めた。正面で見える別部品間の交線は2,480.9 mmから223.2 mmへ、同じ接続面内の交線は372.4 mmから0.0 mmへ変わった。0°、−30°、＋30°、−90°、＋90°、180°の順に別部品間の残りは223.23、205.76、208.76、83.95、122.91、0.00 mm。中立の可視交差の測定条件と衣装の隙間は `Head-Fit.json`、白腹の各高さの実測値は `Waist-Fit.json` にある。毛と白い頬の付け根、まぶたと肌の境界には規範と同様に接続が残っている。

`Fit-Mui-Neutral.png` は立ち絵1と中立の斜め、公式の後面アトラスと尾だけの背面を比べる。中立全身のマスクIoUは0.812、背面の尾は0.810。尾全体の幅／高さは公式1.168、モデル1.155。`Fit-Mui.png` では頭を8度傾け6度振り、同じ尾のポーズで初稿と現稿を比較した。参考ポーズ全身のIoUは初稿0.871、現稿0.889。ブローチの青の重心は公式が全高の上から50.30%、モデルが56.04%。頬全幅／全高は公式44.50%、モデル49.17%。前から見える淡桃の尾先面積と、原画で隠れる後頭部の厚みには立体上の解釈がある。

`Eye-Fit.png` は左右の目を原画、以前の左右反転版、現稿、両眼骨を8度回した現稿で並べた。UVセル左から見た白い光の重心は画面左・右それぞれ69.0%、73.7%。Blenderに再読込した実VRMを正面720 pxで撮影すると、青い部分の重心は画面右に2.86 px、2.94 px移動した。点群と画像モデルの追加訓練は各0回。Unityの共通写真とPlay Modeの動作記録は `Corefolder-Training/production-review/` にあるよ。

## 再生成

```powershell
$mui = '100BeautiesLab-CharacterNative/NumberTales/Corefolder-6/Modeling'
$blender = 'C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe'
$database = 'D:/VisualStudio Code Userfile/100BeautiesLab_CreationsDB'
python "$mui/textures_6.py" --database $database
& $blender --background --offline-mode --disable-autoexec --python-exit-code 1 --python "$mui/model_6.py" -- --database $database --out '.cache/mui-rebuild'
```

別の場所にスターターがある場合は `--starter <.blend>` を指定する。テクスチャ生成にはPillowとNumPy、画像測定にはさらにSciPyを使う。`pose_view_6.py`、`fit_report_6.py`、`eye_report.py` にカメラと測定方法を記録したよ。

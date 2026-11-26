# 公式設定画と規範VRMから新しいコアフォルダを作る

**制作の起点は、共通胴体と #4 由来の表情・骨格を持つ編集用素体。** 対象の公式絵でその子の形と色を決め、Tripoのラフで奥行きを確認し、髪・耳・尾・装飾を素体に合わせる。最後に、書き出したVRMそのものをUnityで動かして確かめるよ。ムイ・ヨチカ・イズナ・ハッコの4体を校正した2026-11-26時点の手順だよ。[4体の編集元・VRM・検証結果](production-review/README.md)

## 1. 対象の資料と規範を選ぶ

- 対象番号を決め、CreationsDBの `data/Works_NumberTales/DataBases/db_Primary.json` で公開状態・AI利用可否・配色・`TailsUnit` を照合する。コアフォルダ形態の全身絵、表情違い、尾単体図を開き、尾の本数と分岐、耳の折れ、左右非対称の髪、胸の印や装飾を控える。背面で隠れる房は尾単体図と設定を優先する。入力に使う画像ごとの利用条件も確認してね。
- 規範は #4・#16・#20・#22・#25・#93。それぞれの公式絵と実VRMを対にして見てから、対象に近い**部位**を選ぶ。たとえば骨格と目の位置は #4、顔の輪郭線と胴の陰影は別材質を持つ #22、と出典を分けられる。番号・部位・材質名・参照画像を制作メモに残すと、次回も同じ判断から始められるよ。[規範6体と各公式絵](production-review/reference-pairs.png) ／ [規範VRMとハッシュ](style-training/source-vrms.json)

## 2. 共通素体を起こし、ラフで奥行きを決める

リポジトリ直下のPowerShellで実行する。下の `49` は確認済みの例で、新規制作時は対象番号へ変更する。Blender 5.3.0とVRM Add-on 4.10.5を使ったよ。作業ブランチは `codex-training`。別ブランチが表示されたらそこで止めてね。

```powershell
git branch --show-current
$n = 49
$t = '100BeautiesLab-CharacterNative/NumberTales/Corefolder-Training'
$db = 'D:/VisualStudio Code Userfile/100BeautiesLab_CreationsDB'
$blender = 'C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe'
$work = ".cache/corefolder-$n-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
& $blender --background --disable-autoexec --offline-mode --python-exit-code 1 --python "$t/create_corefolder_base.py" -- --number $n --db $db --style 4 --output "$work/starters"
if ($LASTEXITCODE -ne 0) { throw '素体生成のログを確認してね' }
$starter = "$work/starters/Corefolder-$n/Corefolder-$n-Starter.vrm"
& $blender --background --disable-autoexec --offline-mode --python-exit-code 1 --python "$t/render_corefolder_comparison.py" -- --candidate $starter --output "$work/starter-views"
```

`Corefolder-N-Starter.blend`、同名のVRM、`starter.json` が得られる。顔の前面、眼・口の表情、Humanoid、胴体の左右の変形が出発点。後頭部や個別の髪・尾は次の造形で足すよ。既に同じ資料・ハッシュのStarterがあるならそれを再利用できる。部位別のMToon継承とスターターの詳細は[素体の制作手順](VRM-REUSE-WORKFLOW.md)にあるよ。

| 手元の資料 | Tripoで行うこと | 判断に使う場所 |
| --- | --- | --- |
| 同じ仕様の保存済みGLBがある | 既存のプレビューとGLBを先に開く | 疑問だった側面・背面が読めれば、そのまま造形へ |
| 公式立ち絵だけで特徴が読める | 立ち絵1枚から形状ラフを1件 | 正面の比率、耳先、首飾りの位置 |
| 厚み・後ろ姿・装着位置が曖昧 | 同じ子の整合した複数方向の資料があれば多視点入力。足りない場合は公式絵＋規範VRMの撮影画像＋対象の尾資料から見本を作り、その子の前・左・背・右を展開 | 生成する見本で対象の特徴を確認し、側面の厚みと背面の房の重なりを比べる |

実行入口は `Tools/Tripo/tripo.py`。先に `--list` で対象フォルダを確認し、新規番号なら `100BeautiesLab-CharacterNative/NumberTales/Corefolder-N/` を用意する。API経路は `doctor`・`balance`、初回は承認済みの `--preset draft`。Studio経路はログイン済みの専用Chromeで、残高・見積もり・対象画像を確認する。複数資料の `studio reference` ではプロンプト内で「画像1は対象の外見、画像2は規範の丸みと陰影、画像3は対象の尾」のように役割を指定する。CLIの実引数、見本確認、保存までの例はこちら。[Tripo CLIの実行例](../../../Tools/Tripo/README.md) ／ [ハッコに使った指示と規範画像](../Corefolder-85/Training/StudioReference-20261126/)

**ラフの採否は部位ごとに決める。** ハッコでは多視点版で胸に載る石と後ろへ伸びる尾を側面から読めた。一方、背面中央の大きな房は公式の8本を隠した。ここで尾を再生成し続けず、公式尾図から8本を個別に組む。ラフは `TripoGenerated/` に追記保存し、ジョブID・入力・条件・採用した部位と未確定の箇所を制作メモに残すよ。[同じハッコでの単一画像版と多視点版の比較](production-review/hakko-studio-multiview.png)

## 3. 素体の上に対象の特徴を作る

| 作業順 | 編集する場所 | 次へ進む目安 |
| --- | --- | --- |
| 顔と胴 | Starterを対象の `Modeling/` に別名保存。共通胴を規範 #4 の輪郭に合わせ、顔の外周と後頭部をつなぐ。#4 の肩衣装は固有装備として扱う | 素体だけの正面・側面・背面で頭が閉じ、顔の縁に白線が出ず、胴が丸い。既存の表情キーと目の位置を保っている |
| 髪・耳・尾 | 公式の房の付け根と先端を決め、ラフの側面を厚みの参考にする。尾は設定の段・本数・分岐を根元から対応付ける | 全身を回して髪と瞳の重なりを見る。尾だけを背面から撮り、各房を公式尾図と対応付けられる |
| 装飾 | 襟・腕章・番号・鎖・石を独立した部品として素体に沿わせる。厚み・隙間・傾きの調整は装飾側で行う | 装着時に浮きや貫通がなく、外すと同じ胴と顔が現れる。腕章は曲面での縁の伸び、石は横からの接触を確認 |
| UV・材質 | 顔と表情のUV対応を維持し、規範と同じ1024×1024 RGBA PNGで主色を用意。制作4体は #22 を参考に顔用と個別部位用の2枚に集約。MToonの陰影・輪郭・透過を部位ごとに合わせる | 裸顔で旧前髪のテクスチャが透け残らず、まばたきで瞳やまぶたの絵がずれず、装飾の番号が正しく読める |
| 骨・表情・揺れ | 装飾には接する胴表面のウェイトを転送。頬髪の付け根は頭に追従させ、垂れた部分に揺れを付ける。尾は房ごとに専用骨を割り当てる。顔の頂点対応を保ってまばたき・母音・感情表情を結ぶ | 首と胴を動かしても装飾が追従し、髪が目に刺さらず、停止後に尾と髪が戻る |

**新規番号で個別制作が必要な箇所。** 素体生成以降の造形はキャラごとに行う。新規Starterから始める実装例は[ムイ](../Corefolder-6/Modeling/model_6.py)と[ヨチカ](../Corefolder-49/Modeling/model_49.py)。イズナ・ハッコ用の [Refined版更新処理](upgrade_refined_character.py) は両者の制作済みメッシュを前提にする。スクリプトで新規制作する場合は、[後頭部の毛色](torso_profile.py)、[口・表情の個別設定](face_articulation.py)、[アトラスに収める画像](texture_atlas.py)を対象に合わせてから書き出す。Blenderで手作業する場合も、同じ箇所を元絵と見比べてね。

## 4. 書き出したVRMで合否を決める

1. **構造。** 編集元 `Modeling/Corefolder-N.blend` と対になる `Corefolder-N.vrm` を書き出す。VRM 0.x、規範と同じHumanoid 53スロット、MToon、内蔵テクスチャ、使用条件、表情のバインドを照合する。無効な骨参照・無ウェイト・縮退面を点検し、ウェイトは各頂点の合計1、最大4影響を確認する。次は一般の新規Starterから作った候補を1体だけ調べる例。PythonにNumPy・Pillow・SciPy、Node.jsにKhronos glTF Validatorを用意するよ。[形式・スキン検査の実装](check_character_export.py)

   ```powershell
   $model = "100BeautiesLab-CharacterNative/NumberTales/Corefolder-$n/Modeling/Corefolder-$n.vrm"
   python "$t/check_character_export.py" --db $db --starters "$work/starters" --candidate $n $model --blender $blender --validator '.cache/vrm-5.3-tests/khronos/node_modules/gltf-validator' --out "$work/format-checks.json"
   ```

2. **見た目。** Unityの検証用プロジェクトで同じSHA-256のVRMを読み込む。規範6体と同じ正投影・縮尺・照明で正面／側面／背面、公式絵に近い斜め、裸の素体、着衣、尾だけの背面を撮る。白線は髪を外してUVと透過を、胸の凹みに見える箇所は装飾を外して胴の輪郭・法線と白腹の塗りを調べる。外形の一致率だけではこの2件を判定できないよ。[素体の修正前後](production-review/studio-bare.png) ／ [同縮尺の三面比較](production-review/studio-orthographic.png)
3. **動き。** Play Modeでまばたき、母音、首振り、視線、胴の往復と停止を試す。静止画で隠れた瞳・頬髪の交差は運動中の頂点で確認する。検証用Unityの起動方法と `character-review.json` の例は[撮影条件](production-review/README.md#撮影条件)にあるよ。新規番号では[髪と目の計測対象](production-review/CharacterReview.SpringClearance.cs)に番号を追加し、10姿勢分の結果が実際に出たか確認する。既存の形式検査にも `Outfit`、揺れる髪、尾の命名の前提があるので、アクセサリや揺れ髪のない子はその公式仕様に合わせて判定する。
4. **引き渡し。** 編集元・VRM・主色PNGを対象の `Modeling/` にそろえ、比較画像と検査結果にVRMのSHA-256を添える。制作と検証は `codex-training`、監修後のUnity導入は「Unity周り」の `develop` で行う。Unityに置いたVRMと検証済みVRMのSHA-256が一致すれば、見た目と動きを確認した版を特定できるよ。[リポジトリの運用](../../../AGENTS.md)

次の人に渡す制作メモには「対象番号と設定画の版／部位別の規範／ラフから採用した形／尾の本数・分岐／検証したVRMのハッシュと画像／監修待ちの箇所」を残してね。途中再開なら、たとえばペンダントの浮きは装飾の工程、首振り時だけの頬髪の交差はウェイトと揺れの工程から戻れるよ。

## この順番を選んだ理由

| これまでに試した経路 | 実際に得られたもの | 次の制作で使う判断 |
| --- | --- | --- |
| Point-E追加学習 | 規範6体・600ステップで重みを更新。出力は色付き1,024点。固定サンプルで形状誤差が改善 | 大まかな形状条件を研究するときに使う。通常制作は保存済みの共通胴と顔から始める。[点群の学習記録](README.md) |
| SDXL作風LoRA | 規範の撮影画像と対象の生成三面図で400ステップ学習。顔・腕章の文字・尾数には揺れが残った | 見本の作風を試すときに使う。個々の新規制作で再学習する工程は省ける。[画像学習の評価](style-training/REVIEW.md) |
| Tripo頭部を直接使った #57・#85 | 尾とウェイトは動いたが、この版で動作した顔表情は両者とも0 | ラフから厚みと配置を読み、顔のトポロジーと表情はStarterから引き継ぐ。[頭部置換の検証](../../../Tools/Tripo/FIT-REVIEW-20260910.md) |
| 共通素体＋個別造形＋Unity校正 | 4体の編集用BlendとVRMを保存。校正版は各10条件で髪などの揺れ物と目の重なりが0画素 | この経路を標準にし、差が出た部位だけ一段戻って直す。[校正版の計測](production-review/studio-calibration.json) |

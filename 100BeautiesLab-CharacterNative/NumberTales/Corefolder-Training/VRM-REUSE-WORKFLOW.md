# 既存モデルを使ったコアフォルダの別デザイン制作

公式資料の準備からTripo・個別造形・Unity検証まで通して進めるときは、[新しいコアフォルダの制作手順](PRODUCTION-WORKFLOW.md)を使ってね。このページは素体生成と、骨・表情・材質を再利用する条件の詳細資料だよ。

2026-11-25 調査。二春、私なら共通胴体の制作データから始めて、対象の公式資料と形が一致する部位だけを引き継ぐよ。胴体のウェイト、顔の表情、VRM の設定は、それぞれ再利用できる条件が違うんだ。

## 別番号の編集用素体を作る

番号、公式DBの場所、胴体と顔の陰影をどの規範材質から取るかを選んで実行するよ。共通胴体、#4 の制作元の骨格・顔の UV・表情キーから始める。各部位で引き継ぐ MToon 設定は影の境界位置・硬さ、間接光、輪郭のモード・幅・照明との混合率の6項目。公式パレットに主色が複数ある場合もあるため、色は作業用の灰色から始め、部位と色の対応を公式絵で決めるよ。 [素体生成スクリプト](create_corefolder_base.py)

リポジトリ直下の PowerShell で実行する例だよ。#49 の例では #22 の2材質を個別に指定して、胴体に輪郭を付け、顔の輪郭をオフにする。これは設定を引き継ぐための技術試験で、#49 の最終材質は君の監修で決めるよ。

```powershell
$blender = 'C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe'
$training = '100BeautiesLab-CharacterNative/NumberTales/Corefolder-Training'
$db = 'D:/VisualStudio Code Userfile/100BeautiesLab_CreationsDB'
$out = '.cache/corefolder-review-01'
& $blender --background --disable-autoexec --offline-mode --python-exit-code 1 --python "$training/create_corefolder_base.py" -- --number 49 --db $db --output $out --style 22 --material 'CoreFolder022.001' --face-material 'CoreFolder022-2.001'
& $blender --background --disable-autoexec --offline-mode --python-exit-code 1 --python "$training/render_corefolder_comparison.py" -- --candidate "$out/Corefolder-49/Corefolder-49-Starter.vrm" --output "$out/views"
```

- **編集用データ**は新しい `Corefolder-番号/` に保存するよ。`.blend` には公式の全身画像と、DBに画像がある場合は尻尾図をパックする。書き出す `.vrm` は胴体・顔・骨格だけに絞る。台帳 `starter.json` には規範モデル・材質名・ハッシュ、公式画像の出典、尻尾の設定、実際の検査値が入る。すでに同番号の出力があるときは新しい出力先を指定しよう。
- **作風の比較**は正面・側面・背面を Blender EEVEE の同一正投影・世界縮尺・照明で並べるよ。複数の `--candidate` を渡せる。規範は実VRMから毎回描画し、入力と寸法を `comparison.json` に記録する。顔・頬のテクスチャ、髪、耳、尻尾、付属品を公式資料へ合わせた段階でも同じ手順で撮影してね。Unity の最終的な陰影と輪郭は既存の URP 撮影条件で比較するよ。 [三面比較スクリプト](render_corefolder_comparison.py) / [Unity の撮影条件](style-training/captures/capture-manifest.json)
- **胴体の左右の動き**も書き出し時に確かめるよ。#4 の胴体には左右両側に右脚・右つま先のウェイトがあり、元の転送方法では左脚を15度曲げたときの最大頂点移動が0だった。新しい共通素体では、左側に既存ウェイトがない場合だけ、対象のウェイトを左右の実ボーン位置に沿って配分する。各頂点の合計が1のままであること、左右の脚とつま先の変形、中立姿勢への復帰を検査する。形・骨・個別装飾に左右差がある完成モデルへ一括適用する処理ではないよ。

三面図の側面を見ると、素体の頭は表情用の顔の前面だけで、後頭部は開いているよ。**制作を続けるとき**は、対象の顔立ちに合わせて顔の Basis と各表情を調整し、公式絵に沿って後頭部・髪・耳・尻尾・付属品と部位別のテクスチャを作る。追加した髪や尻尾は専用骨とウェイトを付けてから Spring Bone を設定する。顔を差し替える場合は、下の「頂点対応が変わった顔の表情」の手順が使えるよ。

比較ツールは規範6体と、生成台帳のハッシュに一致する素体をそのまま撮影できる。編集後に再出力した自作VRMでアドオンが利用条件の確認を求めた場合は、そのVRMのMetaを確認してから `--accept-candidate-license` を指定するとローカル撮影を続けられるよ。

## 手元のモデルで再現できたこと

**#4 のまばたきは、#57・#85 の Refined 版の顔へ転送できたよ。** 3体の制作データでは顔が各926頂点・1,000面で、すべての面を順番に比較すると構成頂点の番号列が一致した。Blender 5.3.0 の別プロセスで #4 の `EyeClose` を指定し、各 Refined の顔に標準の **Transfer Shape Key → Offset** を実行したところ、どちらも519頂点が動くキーが追加され、元のキーとの頂点変位差は全頂点・全軸で0だったよ。#4 → #16 も同じ操作を試し、頂点数の相違でスキップされることを確認した。検査はメモリ上で行ったよ。閉眼時の見た目と新しい VRM の書き出しは今回の試験範囲外だよ。 [#4 の制作元](../Corefolder-4/VRCModel_CoreFloder-4.blend) / [#57・#85 の Refined 版と既存の動作検証](REFINED-REVIEW.md)

転送先には既存の `EyeClose` があるため、試験で追加されたキー名は `EyeClose.001`。こちらを採用するときは、VRM のまばたきが新しいキーを参照するように登録し、書き出したファイルで目が閉じるかを見るよ。

規範6体の制作元にある顔メッシュと、実 VRM の JSON を読み取った結果だよ（2026-11-25 確認、対象ファイルの更新日は UTC で 2026-09-09）。全6体の `specVersion` は `0.0`、Humanoid 登録は各53骨、材質のシェーダーはすべて `VRM/MToon`。表情グループ欄の括弧内は、メッシュのモーフを参照する `binds` が1件以上あるグループの数だよ。 [規範VRMのパス一覧](style-training/source-vrms.json) / [制作元とメッシュ名の一覧](../../../Tools/Tripo/native-inspection-20260910.json)

| 規範 | 顔の頂点数 | 顔のキー数（Basis を除く） | VRM の表情グループ（モーフ参照あり） | Spring Bone グループ |
| --- | ---: | ---: | ---: | ---: |
| #4 | 926 | 15 | 17（13） | 1 |
| #16 | 1,224 | 15 | 18（13） | 5 |
| #20 | 2,075 | 15 | 18（12） | 4 |
| #22 | 2,181 | 14 | 17（12） | 1 |
| #25 | 1,830 | 15 | 18（13） | 5 |
| #93 | 1,825 | 15 | 17（13） | 3 |

6体とも顔の頂点数が異なるので、規範同士で顔全体のキーを頂点番号のまま移す方法は使えないよ。対象デザインに合う顔があれば、その複製のまぶたや口まわりの頂点対応を保って造形するのが第一候補。#57・#85 の Tripo 頭部に差し替えた `structure-v4` は、同じ番号の Refined 版とは制作経路が違い、過去の検査では動作する顔表情が両方とも0だったよ。規範6体の VRM には揺れ物のコライダーグループも各0件なので、髪や尻尾の体への接触を避けたいモデルでは個別に調整しよう。 [Tripo 頭部に差し替えた版の検査記録](../../../Tools/Tripo/FIT-REVIEW-20260910.md)

## 制作に使う版とスキル

- **Blender 側**。Steam 版 `5.3.0` に公式の Extension 版 `4.10.5` を導入したよ。配布 ZIP の SHA-256 は `5f0dd6a277f33961cc453ca401d36ae99272f6bcd06994e8c375d2b922b44bf1`。別プロセスでも `bl_ext.blender_org.vrm` の有効化を確認し、規範6体を各々インポート → 一時VRMへエクスポート → 空のシーンへ再インポートした。6体とも VRM 0.0、同じ53種の Humanoid スロット、表情グループ名とモーフバインド件数、揺れ物グループ別の起点数、MToon シェーダーを保持したよ。輪郭幅の最大絶対差は約 `9.5e-9`。 [公式配布版](https://github.com/saturday06/VRM-Addon-for-Blender/releases/tag/v4.10.5) / [公式の導入手順](https://vrm-addon-for-blender.info/ja-jp/installation/)
- **Unity 側**。プロジェクトは Unity `6000.3.23f1`、UniVRM の 0.x 用と 1.0 用をともに `0.131.1` に固定しているよ。既存の Codex スキル `unity-mcp-orchestrator` と、設定済みの MCP for Unity `10.1.2` は、対象プロジェクトの比較シーン撮影・Console 確認に使える。#57・#85 の検査コードにはウェイト合計、骨を曲げたときの頂点の追従、まばたき・口・笑顔の変形を見る先例があるよ。スクリプトの対象番号と期待値はこの2体専用だよ。 [Unity の版](../../../ProjectSettings/ProjectVersion.txt) / [パッケージ設定](../../../Packages/manifest.json) / [既存の検査コード](check_refined.py) / [UniVRM の該当リリース](https://github.com/vrm-c/UniVRM/releases/tag/v0.131.1)

## 一次資料で確認できたこと

| 再利用するもの | 使える条件と注意点 |
| --- | --- |
| 胴体・骨格・既存パーツ | 元の `.blend` があれば、別名の制作ファイルで編集できる。別ファイルの部品は Blender の **Append** でローカルに取り込めるよ。対象固有に変えるメッシュ・材質・画像の共有先と、Armature モディファイアが指す骨格を確認する。`.vrm` しかない場合は VRM Add-on で読み込み、復元されたメッシュ・ボーン・設定から始める。 [Blender の Link / Append](https://docs.blender.org/manual/en/4.5/files/linked_libraries/link_append.html) / [VRM Add-on の機能と入出力](https://vrm-addon-for-blender.info/ja-jp/) |
| 標準のウェイト転送 | 例として胴体から新しい衣装へ移すなら、レスト姿勢・縮尺・位置を合わせ、**衣装側** に Data Transfer を置く。Source に胴体、Vertex Data に Vertex Groups、対応に Nearest Face Interpolated、グループ対応に名前を指定する。必要なら Generate Data Layers で転送先の層を作る。異なる頂点数でも最近接面の頂点ウェイトを補間できるよ。脇・指の間・二重の布では別部位が近くなるため、転送範囲を絞り、曲げた姿勢で修正する。 [Blender の Data Transfer](https://docs.blender.org/manual/en/4.5/modeling/modifiers/modify/data_transfer.html) / [最近接面補間の実装上の定義](https://github.com/blender/blender/blob/v4.5.0/source/blender/makesrna/intern/rna_modifier.cc) |
| 同じ頂点対応を持つ顔の表情 | 共通の顔から頂点順を保って形を変えた場合、元の顔でキーを指定し、対象の顔を最後に選択して **Transfer Shape Key → Offset** を使えるよ。Blender 4.5 の実装は、対象の Basis の頂点に、同じ番号の元頂点の「キー座標 − 元の Basis 座標」を加える。頂点数が違うとスキップする。同数でも並び替えや左右の対応違いがあれば意図した表情は出ない。**Join as Shapes** は選択物の頂点位置をキーにする操作なので、対象の顔を変形させた複製を戻すときに使える。 [Blender の Shape Keys Panel](https://docs.blender.org/manual/ja/4.5/animation/shape_keys/shape_keys_panel.html) / [Blender 4.5 の ShapeTransfer 実装](https://github.com/blender/blender/blob/v4.5.0/scripts/startup/bl_operators/object.py) |
| 頂点対応が変わった顔の表情 | 対象のまぶたや唇を動かして、対象メッシュにキーを作るのが確実だよ。面の位置がよく合う場合は **Surface Deform** も試せる。ニュートラルの元の顔へ対象の複製を Bind し、元の表情を一つずつ動かす。その都度、評価後の対象メッシュを同じ頂点順の形状として採取し、対象の Basis に Join as Shapes で戻す。駆動側に重複頂点・凹面・3面以上が接する辺があると Bind に失敗しうる。上下の唇やまぶたが独立して動くか、一つのキーで試してから広げよう。 [Blender の Surface Deform](https://docs.blender.org/manual/en/latest/modeling/modifiers/deform/surface_deform.html) / [Shape Keys Panel](https://docs.blender.org/manual/ja/4.5/animation/shape_keys/shape_keys_panel.html) |

**VRM 固有の登録。** VRM Add-on が保持する Humanoid の各スロットには実際のボーンを割り当てる。Meta に対象の名称・作者・利用条件を設定し、Look At と First Person を使うモデルでは目線・一人称表示も照合する。VRM 1.0 では Humanoid と Meta は必須で、Expressions、Look At、First Person は任意だよ。アーマチュアの複製やメッシュの差し替え後は、参照先が対象モデルの実体を指しているかを見る。 [アドオンの公式設定例](https://vrm-addon-for-blender.info/ja-jp/scripting-api/) / [VRM 1.0 仕様](https://github.com/vrm-c/vrm-specification/blob/master/specification/VRMC_vrm-1.0/README.ja.md)

**表情・揺れ物・材質。** 0.x の BlendShapeGroup と 1.0 の Expression は、VRM の表情名と実際に変形するメッシュ／モーフを結びつける。1.0 の morphTargetBind は対象ノード・モーフ番号・強さを持つので、顔交換後は各バインドを再確認しよう。揺れ物は対象の髪・尻尾にある関節列とコライダーの位置を合わせる。MToon は肌・髪など対応する材質を出発点にし、対象のテクスチャ・影色・輪郭幅を同じ照明で確認する。 [VRM 0.x 仕様](https://github.com/vrm-c/vrm-specification/blob/master/specification/0.0/README.md) / [VRM 1.0 の表情バインド](https://github.com/vrm-c/vrm-specification/blob/master/specification/VRMC_vrm-1.0/expressions.md) / [SpringBone](https://vrm.dev/vrm1/springbone/) / [MToon の設定](https://vrm-addon-for-blender.info/ja-jp/material-mtoon/)

**追加ツールの候補。** 標準転送で衣装の反対側や腕のウェイトを拾う場合、Robust Weight Transfer は試す価値があるよ。論文の手法は距離と法線の角度から信頼できる表面対応を選び、残りのウェイトを補間する。用途はスキニングで、表情作成・骨の追加・VRM 登録は別工程。Blender アドオンの配布物は Blender／Python の版と環境で異なるので、必要になった段階で同じ衣装・同じポーズによる標準転送との比較で採否を決めよう。 [著者による論文](https://www.dgp.toronto.edu/~rinat/projects/RobustSkinWeightsTransfer/preprint.pdf) / [アドオン開発元の配布条件](https://github.com/sentfromspacevr/robust-weight-transfer/releases)

## このプロジェクトで試す順番

1. **比較元を選ぶ。** 対象の形・色・尻尾の本数・付属品を CreationsDB の公式資料で確認する。作風は #4・#16・#20・#22・#25・#93 の実 VRM と対応する制作データを参照し、胴体は `100BeautiesLab-CharacterNative/Basis/Corefolder/VRCModel_CoreFloder-Base.blend` から始める。#4 の肩衣装は #4 固有。採用する部品ごとに出典パスと変更内容を記録する。 [リポジトリの制作規範 §9.1](../../../AGENTS.md)
2. **小さく試す。** 共通胴体の複製に、対象資料から選んだ一部位を合わせる。衣装なら左右で腕を上げて誤ウェイトの場所を記録。顔なら片側のまばたき一つで、頂点対応、閉じたときの隙間、頬への影響を確認する。合格した手順を同じ条件の部位に広げる。 [ウェイト転送](https://docs.blender.org/manual/en/4.5/modeling/modifiers/modify/data_transfer.html) / [表情転送の実装](https://github.com/blender/blender/blob/v4.5.0/scripts/startup/bl_operators/object.py)
3. **出力形式を決める。** 利用先に合わせて 0.x／1.0 を選び、規範と同形式のまま比較できる初回出力を優先する。意図して 0.x から 1.0 に移す場合は、UniVRM の移行手順で別ファイルを作る。UniVRM は Look At の角度カーブを線形に移行し、First Person の親を頭に固定する。対応しない許諾項目や、Shade Texture が未指定の MToon の移行も再確認する。 [VRM の版による違い](https://vrm.dev/vrm1/changed/) / [UniVRM の移行手順](https://vrm.dev/univrm1/migrate_vrm0/migrate_editor/) / [移行時の互換性](https://vrm.dev/univrm1/migrate_vrm0/feature/)

## 対象モデルごとの受入検査

| 検査 | 合格を判断する材料 |
| --- | --- |
| 三面の見た目 | 対象と規範6体を同じ正投影・縮尺・照明・ポーズで正面／側面／背面から撮る。顔・目・頬・髪・尻尾・面の作り・輪郭を並べ、対象資料と一致した箇所と未調整箇所を記録する。 [制作規範 §9.1](../../../AGENTS.md) |
| 骨・ウェイト | 書き出した VRM を対象形式対応の UniVRM へ読み込み、初期姿勢・身長・足の接地を確認。左右の腕上げ、肘・膝曲げで誤追従・めくれ・貫通を調べる。表情や揺れ物を除く姿勢に戻して、メッシュがレスト姿勢へ正しく戻ることも確認する。 [UniVRM の対応形式](https://github.com/vrm-c/UniVRM) / [VRM 1.0 の T ポーズ](https://github.com/vrm-c/vrm-specification/blob/master/specification/VRMC_vrm-1.0/tpose.md) |
| 表情・視線・揺れ | 登録したキーを個別に 0・0.5・1 で確認し、二値表情は意図した切替も確認する。両目の閉じ方、母音、視線とまばたきの同時入力を試す。実行中に頭・胴体を動かして、設定した髪・尻尾が想定の向きに追従し、静止後に落ち着くか見る。 [表情の仕様](https://github.com/vrm-c/vrm-specification/blob/master/specification/VRMC_vrm-1.0/expressions.md) / [SpringBone](https://vrm.dev/vrm1/springbone/) |
| 再読込・記録 | 書き出したファイルを空の Blender シーンと UniVRM の双方で開く。メッシュ・表情の対象・材質の画像・輪郭・作者と許諾が一致するかを見る。対象パス、使用した Blender／アドオン／UniVRM の版、出力の VRM 版、警告と未解決箇所を記録する。 [VRM Add-on の書き出し](https://vrm-addon-for-blender.info/ja-jp/ui/export_scene.vrm/) / [UniVRM](https://github.com/vrm-c/UniVRM) |

同じ生成コードで、#6 は胴体に #16・顔に #4、#49 は胴体と顔に #22 の別々の材質を指定したよ。両方とも Humanoid 53種、実際のモーフを参照する表情13種、胴体と顔の MToon 2材質を出力した。別プロセスの Unity 6000.3.23f1 と UniVRM 0.131.1 では、0.x を 1.0 として読み込む経路で有効な Humanoid と `VRM10/MToon10` を確認した。まばたき・「あ」・笑顔を0から1に変え、BakeMesh の頂点が実際に動くことも確認したよ。Unity試験は独立した検証プロジェクトで実施。上の三面比較は Blender EEVEE の描画で、対象プロジェクトの URP での最終表示は制作後の検査に残しているよ。

旧版で作られた #4 の制作元を開く際、アドオンから材質の表情用ソケットについて警告が出たよ。派生版では現行のノードで作業材質を作り直し、保存した2体の `.blend` を開き直して、両材質の色・透明度・影・輪郭色など7個の表情入力ソケットと、パック済み公式画像（#6 は4枚、#49 は3枚）を確認したよ。

両方の試作について、UniVRM の制御骨を15度曲げて `Runtime.Process()` を呼び、反映後の胴体の頂点座標を測ったよ。最大移動量は左脚が 0.085286、右脚が 0.085290 Unity単位。Blender での検査でも左つま先が 0.052622、右つま先が 0.052630 Blender単位で動き、中立姿勢へ戻った。三面図では肩衣装のない共通胴体と仮の顔を確認できる。固有の配色・目と頬の描き込み・髪・尻尾・付属品は次の造形工程に残っているよ。

## 顔を張り直すときと、書き出した材質を調べるとき（2026-11-25）

- **顔の面を張り直す候補は Retopoflow 4。** PolyStrips は元の顔の表面に沿って四角面の帯を描けるよ。既存の顔を複製しても公式資料の目や口の位置に合わせにくいときは、片目の周りに新しい面を張り、そこで閉眼キーを作って上下のまぶたが閉じるか試せる。開発元の変更履歴で確認できたのは 4.1.9 での Blender 5.2 対応まで。手元の 5.3.0 での動作は未検証なので、今は導入を見送り、対応する版と張り直す対象がそろったときの候補にするよ。 [PolyStrips の操作](https://docs.retopoflow.com/v4/polystrips.html) / [開発元の変更履歴](https://docs.retopoflow.com/v4/changelist.html) / [開発元の配布条件](https://docs.retopoflow.com/v4/installation.html)
- **Khronos glTF Validator** の公式 npm 版 `2.0.0-dev.3.10` を検証用キャッシュに導入して、規範6体と試作2体のVRMをローカルで検査したよ。8体とも glTF エラー0件、警告は旧拡張名 `VRM` の形式について各1件（`INVALID_EXTENSION_NAME_FORMAT`）。MToon の表示と表情の動作は Blender・UniVRM の検査で確認する。 [検査項目と対応拡張](https://github.com/KhronosGroup/glTF-Validator#implemented-features) / [公式ブラウザー版](https://github.khronos.org/glTF-Validator/)
- **外部のエージェントスキル**では、EL4CTEO の `blender-character-rigging` が提示する「骨を動かした後の変形を調べる」手順を胴体検査に取り入れたよ。`blender-retopology-uv` の手動リトポロジーと目・口まわりのループ設計は、元の顔を流用しにくい場合の候補。今回は手順を参照し、この2スキルの自動インストールや Rigify への骨格置換は行っていないよ。 [リギングスキルの原本](https://github.com/EL4CTEO/blender-skills/blob/main/skills/blender-character-rigging/SKILL.md) / [リトポロジースキルの原本](https://github.com/EL4CTEO/blender-skills/blob/main/skills/blender-retopology-uv/SKILL.md)

**規範6体の MToon は、追加ツールなしで数値を比較できたよ。** VRM 0.x の JSON にある `extensions.VRM.materialProperties` の各材質で `floatProperties` を読むと、7材質の輪郭幅モード（`_OutlineWidthMode`）は「なし」が3件、「ワールド座標」が4件。#16 と #20 はどちらも輪郭幅（`_OutlineWidth`）が 0.2 だけど、影の境界位置（`_ShadeShift`）は順に約 0.405 と −1 だった。#22 は2材質のうち片方だけに輪郭がある。書き出し前後の差を見るときも、部位に対応する材質ごとに輪郭のモード・幅・影の値と三面図を照らし合わせよう。 [実測したVRM一覧](style-training/source-vrms.json) / [UniVRM 0.131.1 の材質パラメーター](https://raw.githubusercontent.com/vrm-c/UniVRM/v0.131.1/Packages/VRM/MToon/Shaders/MToon.shader) / [MToon の設定と見た目の関係](https://vrm.dev/univrm/shaders/shader_mtoon/)

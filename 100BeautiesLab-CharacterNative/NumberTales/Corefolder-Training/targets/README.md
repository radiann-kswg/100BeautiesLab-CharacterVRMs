# 57・85のVRM制作基盤

`codex-training` で制作する。Unity操作もこのブランチで行う（ルート `AGENTS.md` §10）。

## 開くファイル

- Blender: `../../Corefolder-57/Corefolder-57-ModelingFoundation.blend`
- Blender: `../../Corefolder-85/Corefolder-85-ModelingFoundation.blend`
- Unity: `Assets/100BeautiesLab-CharacterVRM/NumberTales/ModelingFoundation/Corefolder-57-85-ModelingFoundation.unity`
- 各キャラの `Assets/.../Corefolder-N/ModelingFoundation/` に素体VRMと確認用Prefab。

**完成した57・85のVRMではない。** 共通素体 `100BeautiesLab-CharacterNative/Basis/Corefolder/VRCModel_CoreFloder-Base.blend` の胴体に、#4の骨格・顔・表情を組み合わせた編集用ベース（v2）。モチの肩衣装を含む元Bodyは置き換え済み。顔はまだ#4由来で、各キャラの公式資料に合わせた調整が必要。

## 含まれるもの

- 共通素体bodyをミラー適用・2段階細分化した4306頂点の胴体。元#4 Bodyの最大連結面（裸の胴体1078頂点）だけからウェイトを最近傍ポリゴン補間で転送し、正規化。衣装・付属部位は転送元から除外。
- Body / Face のスキニング、58ボーン、Humanoid対応53ボーン。元#4にあった別部品の手指メッシュも除去したため、Humanoidの指ボーン対応は残るが指の見た目の動作は未実装。
- FaceのBasis＋15シェイプキー。母音・まばたきの変形をUnity上で検証済み。
- 元の4尾のメッシュ・ボーンとSpring Bone設定を除去。新しい尻尾の造形・骨格は未作成。
- 君が収録した三面図と、現行CreationsDBの許可済み画像4点を各Blenderファイルへパック。
- 公式パレットの参照スウォッチ。素体への色分け・テクスチャ作成は未実施。
- 6体で追加訓練済みのPoint-E `all6-v2` に公式コアフォルダ画像を入力した、各1024点の形状参考データ。
- 公式設定・元ファイルと重みのSHA-256・未実施項目を、各 `Training/foundation.json` とBlender内のTextへ収録。

今回のv2変更は**制作ベースの形状とスキニングの修正**。6体から学習した重み・生成点群は変更しておらず、点群には元モデルの衣装の影響が残り得る。

57・85への適用は**学習済み重みによる画像条件付き推論**。57・85の3D正解データを使った再学習ではない。点群から顔・髪・尻尾の正確な形、トポロジー、ウェイトは得られていないため、造形の補助資料として扱う。画像・設定を生成モデルの言語学習に使用したわけではない。

## キャラクターごとの制作チェック

| 対象 | 公式資料で確認する項目 |
| --- | --- |
| 57（イズナ） | 狐耳、金髪ポニーテール、琥珀色の目、右肩の57の腕章。尻尾7本。DBのBranchesは上側 TailCount 5 / ClusterCount 2、下側 TailCount 2 / ClusterCount 1。 |
| 85（ハッコ） | 狐耳、茶髪ポニーテール、シアン系の目、雫型ペンダント。尻尾8本。DBのBranchesは上側 TailCount 3 / ClusterCount 1、下側 TailCount 5 / ClusterCount 2。 |

Branchesの値はDBの記述をそのまま保持している。TailCountとClusterCountを掛けて総数を増やさない。位置・向き・束ね方は三面図・設定資料で確認して造形する。85のコアフォルダ番号表示位置を新たに設定していない。

## 作業の続き

1. Blenderの `01 Editable neutral base` を編集する。`02 Official references` の追加資料は表示を切り替えられる。
2. 公式三面図と設定に合わせて体形・顔・髪・耳・付属品・尻尾を作り込み、UVと色分けを整える。
3. 尻尾の骨格・ウェイトと揺れ物を設定し、15表情を新しい顔に合わせて調整する。
4. **素体のArmatureと完成させたメッシュだけを選択してVRM出力**する。参考画像・パレット・文字・AI点群を出力に含めない。
5. UnityでHumanoid、表情、揺れ物、表示を確認してから完成版とする。現在のVRMはタイトルにunfinishedを明記し、#4の作者・利用条件を継承している。

## 再実行と検証

以下はリポジトリルートから実行する。Blenderは起動中のファイルを置き換えないよう別プロセスを使う。`foundation.py` は今回の生成物を再作成するため、**造形を始めたファイルには再実行しない**。編集版は別名で保存する。

```powershell
$training = '100BeautiesLab-CharacterNative/NumberTales/Corefolder-Training'
$blender = 'C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe'
# sample57-v1 / sample85-v1 の推論結果が既にある場合
& $blender --background --python-exit-code 1 --python "$training/foundation.py"
& $blender --background --python-exit-code 1 --python "$training/check_foundation.py"
```

画像収録の再実行は `collect_db.py --ids 57 85 --output "$training/targets"` に既存の `--db` と `--manifest` を指定する。既定の6体の学習データは変えない。

推論結果がない場合は既存 `train.py` に `--run sample57-v1`（85はsample85-v1）、`--steps 0`、`--checkpoint "$training/runs/all6-v2/checkpoint.pt"`、`--sample-image "$training/targets/db-assets/Corefolder-57/emstk_corefolderNTS-57-1.png"`（85は85へ置換）を指定する。既存のrunは上書きしない。チェックポイントはGit対象外なので、別PCでは元の学習手順で用意する必要がある。

`unity-foundation.cs` はOSS Unity MCP `execute_code` に渡すメソッド本体で、Assets内に置くC#クラスではない。確認シーンが既に存在する場合は再作成せずシーンを開く。カメラとライトだけの未変更初期シーンは置き換え、それ以外の保存済みシーンには追加で開く。

v2では、共通素体の加工後の全頂点座標との一致、全頂点のウェイト正規化、背骨回転への追従も検証済み。元#4・共通素体・元VRM6体は変更していない。v1のBlenderファイルと生成履歴はローカル `.cache/foundation-v1-backup/` に退避。

検証結果: `foundation-checks.json`（ファイル・骨格・表情・素材・元VRMのハッシュ）、`unity-checks.json`（Humanoidと口/まばたきの頂点変形）。

ローカルRTX 5060 Tiで処理。今回のクラウド使用・費用は0円。

Unityのv2確認ではエラー0件。VRM0からの移行通知2件とRenderQueueの既定値使用警告2件が出ている。表示・Humanoid・口/まばたきの動作を確認済み。最終マテリアル設定はキャラ固有テクスチャ制作時に再確認する。

# 57・85 実VRM メッシュ／材質推敲（2026-09-09）

`codex-training` の試作改訂版。実メッシュと材質を変更し、BlenderからVRM 0.xを書き出してUnityのOSS MCPで読み込み・撮影・Prefab保存を実施した。完成承認済みモデルではない。

## 成果物

| キャラ | 編集可能なBlender | 実VRM / Prefab |
| --- | --- | --- |
| 57 イズナ | [Corefolder-57-Refined.blend](../Corefolder-57/Corefolder-57-Refined.blend) | `Assets/100BeautiesLab-CharacterVRM/NumberTales/Corefolder-57/Refined/` |
| 85 ハッコ | [Corefolder-85-Refined.blend](../Corefolder-85/Corefolder-85-Refined.blend) | `Assets/100BeautiesLab-CharacterVRM/NumberTales/Corefolder-85/Refined/` |

Unity比較シーン: `Assets/100BeautiesLab-CharacterVRM/NumberTales/Refined/Corefolder-57-85-Refined.unity`

![公式DBと実VRM](targets/Refined-Unity-overview.png)

## 参照と実際の変更

- 作風・顔のUVと表情・MToon表現は既存VRM #4,16,20,22,25,93を規範にした。共通素体由来の胴体を最大12%横に広げ、腹の白いメッシュも追従。#4の肩衣装は含めない。
- 顔のベースは#4の既存UVとテクスチャ。57の虹彩には同UV領域の#20の琥珀色テクスチャ、85は#4のシアンの虹彩を使用。#4固有のシアンの裏面を白くし、全材質をMToonに戻した。
- `100BeautiesLab_CreationsDB/data/Works_NumberTales/DataBases/db_Primary.json`、`Images/DB_Primary/corefolder/{57,85}/`、`attr/tailsUnit/`を部位ごとの基準にした。個別画像とDBのSHA-256は各キャラの `Training/refined-model.json` に記録。
- **57**: 公式尻尾図の上5房・下2房、二股の先端、中央の短い房を閉じた立体メッシュに再構成。キャラ右側のポニーテール、金髪・琥珀の目を反映。右肩の腕章は公式 `attr_numberMarkNTS-57.png` を改変せずにパックし、曲面の白い布、黄緑の縁、留め具を作成した。
- **85**: 公式尻尾図の上3房・下5房と下側の広がりを再構成。茶色の髪、頂部の尖った毛束、左右で傾きの違う耳、右側ポニーテール、伏せ気味のシアンの目、淡い紐と水滴型のペンダントを反映した。
- 目の開きは既存のBasisと全表情キーに対応する変換を施した。尻尾は各房に3本の変形骨を付け、胴体へつながる根元を作った。尾先の色境界はポリゴン単位の粗い塗り分けを避けるため、境界でメッシュを分割した。
- 公式2D画像から厚み、奥行き、骨の配置を解釈している。生成三面図と公式尻尾図が異なる部分は公式図を優先した。Unity比較シーンでは生成三面図を非表示で残し、公式全身画像と尻尾図を表示している。

## 三方向の実VRM確認

| 57 正面 | 57 側面 | 57 背面 |
| --- | --- | --- |
| ![](../Corefolder-57/Training/Refined-front.png) | ![](../Corefolder-57/Training/Refined-side.png) | ![](../Corefolder-57/Training/Refined-back.png) |

| 85 正面 | 85 側面 | 85 背面 |
| --- | --- | --- |
| ![](../Corefolder-85/Training/Refined-front.png) | ![](../Corefolder-85/Training/Refined-side.png) | ![](../Corefolder-85/Training/Refined-back.png) |

撮影はUnity上の実VRMを一時的にBakeMeshし、共有MToon材質のまま正投影1024×1024、白い主光、環境光0.6、背景0.75で実施。規範6体の `style-training/captures/` と同じ照明条件。画像は生成AIによる補正をしていない。

## 検証

`check_refined.py` と `targets/refined-model-checks.json` に再実行可能な検証と結果を保存。

- #57: 32メッシュ、79骨、尻尾7房（上5・下2）。#85: 32メッシュ、82骨、尻尾8房（上3・下5）。
- いずれもHumanoid 53骨、15表情。全頂点の座標が有限、変形ウェイトの合計が1、参照先の骨が存在。
- 各尻尾メッシュの全エッジがmanifold。全房の中間骨を0.12rad回転させ、実際の頂点変形を確認。
- `a`、`EyeClose`、`Joy` の評価済みメッシュが変形することを確認。最終保存データはニュートラル状態。
- 全VRM材質が `VRM/MToon`、顔・虹彩のテクスチャ参照あり。Unityでは `VRM10/Universal Render Pipeline/MToon10` として読み込み。
- 規範6体のVRM、前段のModelingDraft、共通素体、参照した創作DBファイルのハッシュ一致を確認。元アセットの上書きなし。
- Unity ConsoleのErrorは0件。UniVRMのVRM 0→1移行・RenderQueue既定値へのフォールバック警告は残る。実表示は確認済み。

## 残る造形上の差と限界

- 顔・前髪の接合部、目の形、耳の断面、側面の尻尾の厚みと房同士の接触は、公式図との細部差が残る。2D図から作った背面配置であり、全方向の見栄えまで完成承認したものではない。
- 尻尾の変形骨はあるが、SpringBone・揺れ物コライダーは未調整。通常の静止表示と基本変形を確認した段階。
- 三面図からの画像LoRA追加学習は前段で完了しているが、今回のメッシュは学習モデルが自動生成した完成形ではない。公式DBと規範VRMを参照し、スクリプトで直接造形・材質を編集した。今回のクラウド利用は0円。

## 再生成

別のBlenderプロセスで `refine_models.py` を実行すると前段のModelingDraftから修正版を再生成する。`db_refinement.py` にDBに対応する房の輪郭、顔と付属品の調整を記録した。保存したRefinedファイルに手作業を加えた場合は、再生成前にそのファイルを別名保存すること。

UnityはアセットをRefresh後、`unity-refined.cs` → `refined_db_boards.cs` → `capture_refined.cs` の順で実行。シーンに未保存変更がある場合は読み込み処理が停止する。今回のコミット・pushは実施していない。

# 57・85 Tripoモデルの構造調整

2026-09-10。作業ブランチ `codex-training`。今回の到達点は編集用Blenderモデルの構造調整。規範と同等の完成VRMではない。

## 現在のファイル

- `100BeautiesLab-CharacterNative/NumberTales/Corefolder-57/Tripo/Corefolder-57-TripoFit-structure-v4.blend`
- `100BeautiesLab-CharacterNative/NumberTales/Corefolder-85/Tripo/Corefolder-85-TripoFit-structure-v4.blend`

User指定の正しい保存規則は `100BeautiesLab-CharacterNative/<作品>/<種別>-<Num>/Tripo/`。余分な `Corefolder/` 階層は設けない。今回の中間blendは各 `Tripo/Iterations/` へ保存済み。移動前後のハッシュ一致を確認し、result.jsonの参照も更新。Iterationsには失敗した切り出し・色分け試行も含むため、現在の編集には上記structure-v4を使う。

## 実施した変更

- 規範6体（4・16・20・22・25・93）の実VRMと制作blendを確認。各blendのメッシュ、寸法、材質名、骨数、シェイプキーを `native-inspection-20260910.json` に記録。
- Tripoの頭部を切り出し、UV境界の重複頂点を統合。向きをBlenderの-Zではなく **Z-up / -Y-front** に合わせて、各キャラ別に高さを調整した。
- 頭部はボクセルリメッシュとDecimateで軽量化。これは表情用の手作業リトポロジーではない。微小な孤立面を除去し、頭部の境界辺・非多様体辺が0であることを確認。
- 胴体は各既存 `Corefolder-N-Refined.blend` のBodyを再利用。元をたどると共通素体 `Basis/Corefolder/VRCModel_CoreFloder-Base.blend`。#4固有の肩衣装は含まない。
- 既存Refinedで公式尻尾図から造形した独立メッシュを再利用。57は上5＋下2、85は上3＋下5。今回の現行DBと原本の尻尾図でも本数を照合した。
- 尻尾を1段階細分化し、各3ボーンのウェイトを保持。頭部はheadボーンへ剛体的に追従。首のつなぎ面を追加し、腹部の重ね面の表示干渉を軽減。
- 57の腕章・85のペンダントは既存Refinedのものを保持。頭部の自動色分けは位置ずれのため不採用とし、頭部は中立色のMToon仮材質。正しいUV・色塗りは未実施。
- 元のFaceをこの派生版から除いたため、無効な表情バインドも除去。既存Refinedの表情は元ファイルに保持しているが、今回のTripo頭部にはまだ移植していない。

## 出典

Tripo task: 57=`19c61367-3049-48a4-820c-27bef05ed89d`、85=`a1155703-ffc7-4ee3-a4a6-1abc253633fe`。raw GLBは前回の `TripoGenerated/` に保持。

骨格・胴体・尻尾・付属品の直接の再利用元は各 `Corefolder-N-Refined.blend`。その制作履歴は各 `Training/refined-model.json` と `Training/foundation.json`。#4由来の基礎骨格、共通素体由来の胴体、公式尻尾図由来のメッシュを再利用した。規範6体のファイル、Refined元ファイル、Tripo raw GLBはハッシュ照合で変更なし。

公式資料: CreationsDB `data/Works_NumberTales/DataBases/db_Primary.json`、`Images/DB_Primary/attr/tailsUnit/attr_tailsUnitNTS-57.png` と85、入力原本のcorefolder画像。

## 検証結果

`check_reference_fit.py` を保存済みファイルに対して実行し成功。

| 項目 | 57 | 85 |
|---|---:|---:|
| 全体ポリゴン（Blenderの面数） | 約44,900 | 約46,600 |
| 独立した尻尾 | 7 | 8 |
| 骨格ボーン | 79 | 82 |
| ウェイト検証済みメッシュ | 17 | 16 |
| 動作する顔の表情 | 0 | 0 |

全頂点の座標が有限、ウェイト合計1、参照するボーンの存在を確認。胴体・頭部・各尻尾のボーンを0.12rad動かし、実際に頂点が変形することを確認してから元の姿勢へ復帰。頭部と全尻尾の境界辺・非多様体辺は0。全身の接触・自己交差や激しいポーズでの破綻を保証する検査ではない。

詳細: 各キャラの `Training/TripoFit-structure-v4/result.json` と `checks.json`。

## 比較画像

- `reviews/fit-structure-57-85.png`: 調整した2体の正面・側面・背面。
- `reviews/fit-structure-comparison.png`: 調整2体＋規範6体。

同じWorkbenchの単色スタジオ陰影・正投影・最大寸法正規化で撮影。色・MToon・輪郭線の最終見た目を比較する画像ではない。微小な孤立面除去と首の接続面の位置修正後に、現在の保存版を再撮影している。

## 未完了の調整

- 頭部の凹凸はまだTripo由来。イラストの目・頬・口の線が立体化しており、規範の顔の面構成と異なる。中立表情、まばたき・口形状、顔テクスチャの移植・再構成が必要。
- 耳・髪・ポニーテールの形と位置、首周りの段差、尻尾の厚みと重なりは制作解釈が残る。特に側面の頭部接続と背面の尻尾の膨らみを詰める。
- 頭部UVと色塗り、材質ごとのMToon陰影・輪郭、揺れ物（Spring Bone）、UnityでのVRM検証は未実施。
- 顔・髪の見た目と表情が仕上がるまで完成VRMとして出力しない。今回UnityのAssetsには追加していない。

点群追加学習・画像作風学習は今回実行していない。Tripoの追加API利用・追加課金もなし。実施したのはローカルの造形・構造調整と検証。

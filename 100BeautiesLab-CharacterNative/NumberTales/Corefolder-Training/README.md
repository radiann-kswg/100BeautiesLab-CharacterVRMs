# コアフォルダ：ローカル3D追加学習基盤

2026-09-09。Point-E base40M の**既存学習済み重みを実際に更新した試験基盤**。
生成結果は1,024点の色付き点群であり、完成VRM・自動モデリングシステムではない。
新キャラクターの細部、骨格、表情、MToon、揺れ物は今後の制作工程で整える。

## 作成済み

- VRM 6体：4 / 16 / 20 / 22 / 25 / 93。原本・編集元blendは変更なし。
- `dataset-v1/`：各体32,768表面点、8方向画像、GLB、元VRMのSHA-256・ライセンス・正規化情報。
- `db-assets/`：創作DBのコアフォルダ画像15枚を学習条件に追加。設定画・カタログ9枚は確認用。
- `db-references.json`：現行DBの配色・尻尾構成・外見情報、許可済みAIHints、出典とハッシュ。
- 設定テキストは参照・評価条件として利用。Point-Eの言語理解や設定文自体を追加訓練したものではない。
- 人型画像・複数キャラ入りイラストは、誤った画像と3Dの対応を作らないため今回の学習ペアには含めない。
- 未学習キャラの画像は3D正解がないため教師ペアにしない。新規制作時の入力画像として利用できる。

## 試験結果（RTX 5060 Ti 16GB）

| 試験 | 訓練対象 | 更新 | 固定ノイズ誤差 前→後 | 固定サンプルの点群距離 前→後 |
|---|---|---:|---|---|
| `runs/holdout93-v2/` | 4,16,20,22,25（93は除外） | 200 steps | 0.228823 → 0.227538 | 0.123927 → 0.061155 |
| `runs/all6-v2/` | 6体全て | 600 steps（各100回） | 0.228823 → 0.226208 | 0.123927 → 0.046144 |

点群距離は正規化座標での対称最近傍平均距離。93の正面条件・固定seed・1サンプルのみ。
全6体版の93は訓練データなので汎化評価ではない。改善値は品質保証ではない。
学習ループは約19秒／56秒、計測GPUメモリのピークは約2.09GiB（PyTorchのallocated値）。
重み更新・保存・読み戻しを検証済み。クラウド使用額0円、許可予算3,500円は未使用。
細部の再現は未達。クラウドへの切替だけで6体という独立形状数や設定理解の制約は解消しない。

## 再実行

以下はこのUnityリポジトリ直下のPowerShellで実行する。

```powershell
$work = '100BeautiesLab-CharacterNative/NumberTales/Corefolder-Training'
$python = '.cache/point-e-venv/Scripts/python.exe'
# 初回セットアップ時のみ（Python 3.12、uvが必要）
uv venv --python 3.12 .cache/point-e-venv
uv pip install --python $python -r "$work/requirements.txt"
# 元モデル不変・画像出典・点群範囲・色変換を確認
& $python "$work/check.py"
# 93を除外した評価。run名は新しい名前にする
& $python "$work/train.py" --run experiment01 --holdout 93 --steps 200
& $python "$work/check.py" --run "$work/runs/experiment01"
# 保存済み6体版から、指定した公式画像を条件に生成
& $python "$work/train.py" --run sample01 --steps 0 --checkpoint "$work/runs/all6-v2/checkpoint.pt" --sample-image '公式画像の絶対パス'
```

`checkpoint.pt`はPoint-Eモデル重み。LoRAファイルではない。
`--checkpoint`で重みを引き継いだ追加訓練も可能。ただしoptimizer・乱数状態を復元する完全再開ではない。
`runs/`と依存環境はGit対象外。再セットアップだけでは今回の訓練重みは復元されないため別途保管する。

データを作り直す場合：
`prepare.py`をVRM Add-on導入済みBlenderの別プロセスから`--id 4`等で実行。
完了済みデータは上書きしない。`--out`で別出力先を指定できる。
`collect_db.py --db <CreationsDBルート> --manifest <manifest-training.jsonl>`でDB資料を再照合。
使った画像は許可済みマニフェストと現行レコードの公開・進捗状態を照合している。
マニフェスト由来AIHintsはそのスナップショットであり、現行DBとの版差は出典ハッシュで追跡する。

## Blender / Unity

Blender MCP（localhost:9876）の実アドオンに接続し、比較シーンを起動中Blenderへ追加済み。
`runs/holdout93-v2/comparison.blend`を開くと左右で学習前後を比較できる。
`review.py`で生成済み点群から同じ比較ファイルを再作成できる。
既存共通ベースは `100BeautiesLab-CharacterNative/Basis/Corefolder/VRCModel_CoreFloder-Base.blend`。
生成形状の監修後は、このベースと既存6体の骨格・表情実装を参照してVRM制作へ進む。

CodexのVRM学習・制作はUnity操作を含めて`codex-training`で作業（ルート`AGENTS.md` §10）。OSSの `com.coplaydev.unity-mcp` v10.1.2を導入済み。
2026-09-09、Unityをアクティブにした後、パッケージ解決・コンパイル・MCP接続を確認。
接続先は `100BeautiesLab-CharacterVRMs@a6d53b5a`、stdio／ローカルポート6400。
Unity 6000.3.23f1、`ready_for_tools=true`、コンパイル・アセット更新は終了、Consoleのエラー・警告は0件。
6体すべてのVRMファイルをUnity AssetDatabase経由で参照できることを確認した。
4・16・20・25はVRM原本がDefaultAssetとして扱われる旧方式で、対応するPrefabはGameObjectとして正常に読み込まれている。
Unity公式AI MCPは使用していない。VRM出力とUnityへの新規モデル導入はまだ実施していない。

## 出典・扱い

- [Point-E公式](https://github.com/openai/point-e)（MIT）。コード固定: `fc8a607c08a3ea804cc82bf1ef8628f88a3a5d2f`。
- [OSS MCP for Unity v10.1.2](https://github.com/CoplayDev/unity-mcp/tree/v10.1.2)。
- 元作品・資料: [100BeautiesLab_CreationsDB](https://github.com/radiann-kswg/100BeautiesLab_CreationsDB)、RadianN_kswg／百花繚乱研究所。
- アセットは元VRMのMetaとガイドラインを保持。22・93には再配布禁止のMetaがある。データ・重みはローカル検証用途で保管。
- 原作者の2026-09-09の依頼を根拠にVRM読み込みの確認を承認した。元Metaの改変・公開・アップロードはしていない。
- 色の二重ガンマ補正を修正後に作り直した`v2`試験を採用。修正前の試験は`.cache/`へ退避。


## 57・85への制作基盤の適用

[制作基盤の使い方と未実施項目](targets/README.md)。追加訓練済み重みの推論点群、公式資料、共通素体の胴体と#4由来の骨格・顔を持つ編集ベースを個別Blenderファイルに収録。Unity確認用VRM/Prefab/シーンを作成した。完成キャラクターモデルではない。


## 6体の実VRMを規範とする画像の作風学習

[画像LoRAの教材・撮影条件・再実行手順](style-training/README.md)。MToonの透過と輪郭を含む6体の実VRM画像を主教材とし、57・85の生成三面図をデザイン資料として区別する。画像用SDXLへの追加訓練であり、Point-EやVRM自体の造形・材質調整とは別工程。

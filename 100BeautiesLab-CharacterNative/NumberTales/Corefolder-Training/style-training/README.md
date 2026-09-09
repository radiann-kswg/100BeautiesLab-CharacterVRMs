# コアフォルダ画像の作風LoRA

規範は実VRMの **#4・#16・#20・#22・#25・#93**。ルート `AGENTS.md` §9.1 に従う。
これは画像生成用SDXLへの実際の追加訓練で、Point-Eの点群学習とは別の重み。
VRMのメッシュ・UV・骨格・表情・MToonパラメータを自動更新する処理ではない。

## 教材

- 6体をOSS Unity MCPとUnity 6000.3.23f1で正面・側面・背面から撮影した18枚。
- 同じ撮影画像を横に並べた三面図6枚。合計24例を `nt_vrmstyle` の作風教材に使用。
- 57・85の既存生成三面図2枚を `nt_designreference` のデザイン資料として使用。原本の画素は変更しない。
- 学習前処理は画像全体の縦横比を保った正方形へのパディング。人物を切るランダムクロップや左右反転は使用しない。57の腕章の左右を保持する。
- キャプションによる役割分けは完全な学習分離を保証しない。未承認の生成三面図を公式設定や規範VRMの代用にしない。
- `dataset-manifest.json` に全26例の役割・入力ファイル・SHA-256・キャプションを記録。`source-vrms.json` に原本6体の出典を記録。

三面図は `captures/Corefolder-{番号}/three-view.png`。元の1024角画像も保存。
中立灰色背景、正投影、キャラごとに全身を収め、同じキャラの三方向は同じ倍率で撮影。
ライトはカメラに対して同じ角度。元材質の色・テクスチャ・透過を保持したMToon10で描画する。

旧PrefabのUniUnlit材質と、以前のWorkbenchレンダーは教材にしていない。
原本VRMの一時コピーを現行ImporterでMToon10として読み込み、撮影後にコピーを削除した。
PC用URPの `Assets/Settings/PC_Renderer.asset` にMToon公式の `MToonOutlineRenderFeature` を追加して輪郭を描画。
原本VRMのバイト列は不変。VRM0から現行MToonへの移行時には既存Importerの移行警告が出る。
描画環境は再現用に記録しているが、別VRMビューアとのピクセル単位の一致を保証するものではない。

## ローカルで再実行

リポジトリのルートで実行する。既存Python 3.12環境はPyTorch 2.11 / CUDA 12.8、RTX 5060 Ti 16GB対応。

```powershell
$style = '100BeautiesLab-CharacterNative/NumberTales/Corefolder-Training/style-training'
$python = '.cache/point-e-venv/Scripts/python.exe'
uv pip install --python $python -r "$style/requirements.txt"
& $python "$style/setup.py"
& $python "$style/prepare.py"
& $python "$style/check.py"
& $python "$style/train.py" --steps 400 --name style-lora-new
& $python "$style/evaluate.py" --run style-lora-new
```

`setup.py` は固定リビジョンのSDXL base 1.0と公式Diffusers v0.36.0学習スクリプトを `.cache/` へ取得する。
学習スクリプトのSHA-256を実行前に照合。Hubへの重み・画像アップロードは行わない。
重みは `../runs/{run名}/pytorch_lora_weights.safetensors`。出力済み重みの上書きは拒否する。
`runs/` と `.cache/` はGit対象外。今回採用するLoRAは `models/style-lora-v2.safetensors` にも保管し、既存バイナリ運用に合わせてGit LFS管理対象とする。コミット・pushは利用者が行う。
`evaluate.py` は実行フォルダに重みがなければ、この保管済みLoRAを読み込む。

本試験は512角、U-Net LoRA rank 4、batch 1、fp16、gradient checkpointing、学習率0.0001、seed 2026。
テキストエンコーダは凍結。クラウドGPUは使用しない。
全26例を訓練に使うため、学習前後の比較は未見キャラクターへの汎化性能を測る試験ではない。
損失の値だけで作風が合ったとは判断せず、同一seedの生成画像を規範三面図と比較する。

撮影を再実行する場合は、`source-vrms.json` と一致する原本を `Assets/_CodexStyleCapture/Source-{番号}.vrm` にコピーし、UnityでImportする。
現在シーンを保存した状態で、OSS Unity MCPの `execute_code` に `capture-setup.cs`、次に `capture.cs` の内容を渡す。
撮影後はsetupの戻り値にある元シーンを開き、一時コピーのフォルダをUnity AssetDatabase経由で削除する。
一時フォルダは本処理専用。元VRMや既存制作シーンを上書きしない。

## 結果の扱い

[画像付きの実測結果と限界](REVIEW.md)。400ステップの実学習は完了したが、作風・設定の再現は試験段階。三面図を条件にする比較は `evaluate.py --run style-lora-v2 --mode design` で再実行できる。

今回の実行結果・GPU使用量・重みハッシュは `result.json`、学習前後の条件は `evaluation/style-lora-v2-design-1024/comparison.json` を参照。
比較画像は技術検証用であり、57・85の確定デザインや完成VRMではない。

学習後の画像は色面・顔の描き方・陰影の方向を確認する資料として使う。
実モデルへ反映する際は、公式設定の体形・尻尾数・腕章・首飾りを保持し、規範VRMの顔UV、透過ハイライト、MToon、共通素体を参照して造形と材質を調整する。
#4固有の肩衣装を共通仕様として移植しない。

## 公式実装の出典

- [Diffusers LoRAの公式説明](https://huggingface.co/docs/diffusers/training/lora)
- [使用したSDXL LoRA学習コード v0.36.0](https://github.com/huggingface/diffusers/blob/v0.36.0/examples/text_to_image/train_text_to_image_lora_sdxl.py)
- [SDXL base 1.0 モデルカード・ライセンス](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0)

LoRA学習コードはApache-2.0。SDXL重みの利用条件はモデルカードのOpenRAIL++に従う。
作品データの権利・配布条件は各原本に従い、ここでの検証成果はローカルで保管する。

# Tools/Tripo — Tripo AI モデリング用ラッパー

[Tripo AI](https://studio.tripo3d.ai) でイラスト・三面図からベースメッシュを生成するための薄いラッパーです。
運用ルール（承認・禁止事項・成果物の扱い）は **`AGENTS.md` §12** が正典です。

| ファイル | 役割 |
| --- | --- |
| `tripo.py` | 入口。`-c <キャラ>` でキャラクターフォルダを指定し、`scripts/tripo_cli.py` を実行する |
| `scripts/tripo_cli.py` | Tripo 3D Studio（Dropbox `tripo-3d-studio/`）の CLI 複製。差分はファイル冒頭に記載 |
| `config/tripo.yaml` | 既定バージョン・presets（draft / standard / hq / game / parts / print） |
| `requirements.txt` | `tripo3d` SDK ほか |
| `outputs/` `logs/` | `-c` 無しで実行した時の一時置き場（git 管理外） |

## Tripo Studio で画像から校正用GLBを作る（Windows / PowerShell）

リポジトリ直下で実行するよ。Studio用には Python 3.11以上、Google Chrome、日本語UIを使う。最初に専用のChromeプロファイルで普段のStudioアカウントにログインすると、次回もそのログイン状態を使えるよ。プロファイルは `%LOCALAPPDATA%/100BeautiesLab/TripoStudio` に保存される。

```powershell
py -3.12 -m venv .cache/tripo-studio-venv
$studioPython = '.\.cache\tripo-studio-venv\Scripts\python.exe'
& $studioPython -m pip install "playwright>=1.65,<2"
& $studioPython Tools/Tripo/tripo.py studio login
```

ヨチカの公式立ち絵から1件生成する例だよ。CLIが画像、残高、現在価格を表示するので、対象と料金を確認して `y` を入力する。H3.5 プレビュー版・リンク限定公開で、ウルトラメッシュ、テクスチャ、パーツ生成をオフにする。画像は実行場所からの相対パスか絶対パスで指定できるよ。

```powershell
$image = 'D:/VisualStudio Code Userfile/100BeautiesLab_CreationsDB/data/Works_NumberTales/Images/DB_Primary/corefolder/49/emstk_corefolderNTS-49-1.png'
& $studioPython Tools/Tripo/tripo.py -c 49 studio generate $image --max-credits 30
```

生成を受け付けるとStudioのIDとURLを表示する。プレビューを回して形を確認し、保存するモデルごとに `export` を実行してね。次は今回のヨチカを保存する例だよ。

```powershell
& $studioPython Tools/Tripo/tripo.py -c 49 studio export e20cf34b-d67d-41f1-b11a-97c4dfe76324 --date 2026-11-26
```

保存先は `Corefolder-<番号>/TripoGenerated/studio/<日付>/Corefolder-<番号>-<ID>.glb`。日付を省くとPCの当日を使う。既にブラウザで取得したGLBは `studio save <ID> <GLBのパス> [--date YYYY-MM-DD]` で取り込めるよ。どちらもGLBのコンテナとメッシュを検査し、SHA-256を表示する。同じ保存先には追記も上書きもしない。送信後に表示が途切れた場合はStudioのアセット一覧で受付を確認し、既に生成されたIDから `export` で再開できる。

### 規範VRMの撮影画像を添えてラフを作る

Studioの専用プロファイルでログインしてから、公式絵、規範VRMのレンダー、公式の尾資料をこの順で渡すよ。ハッコの試行は Nano Banana、1:1、1枚の見本から正面・左右・背面を作り、H3.5で形状のみを出力した。CLIでは見本と各方向を目視してから次に進める。Studioの画像生成モデルは画面で確認してね。

```powershell
$trial = '100BeautiesLab-CharacterNative/NumberTales/Corefolder-85/Training/StudioReference-20261126'
$art = 'D:/VisualStudio Code Userfile/100BeautiesLab_CreationsDB/data/Works_NumberTales/Images/DB_Primary'
& $studioPython Tools/Tripo/tripo.py -c 85 studio reference "$art/corefolder/85/emstk_corefolderNTS-85-1.png" "$trial/reference-93-front.png" "$art/attr/tailsUnit/attr_tailsUnitNTS-85.png" --prompt-file "$trial/prompt.txt" --max-credits 30
```

## API 経路のセットアップ（Windows / PowerShell）

```powershell
python -m pip install -r Tools/Tripo/requirements.txt
Copy-Item .env.example .env          # リポジトリ直下。TRIPO_API_KEY を記入
python Tools/Tripo/tripo.py doctor   # SDK・キー・ネットワーク確認
python Tools/Tripo/tripo.py balance  # 残クレジット
```

OS の環境変数 `TRIPO_API_KEY` が既にあれば `.env` は不要です（環境変数が優先）。

## 使い方

```powershell
python Tools/Tripo/tripo.py --list                                             # キャラクター一覧
python Tools/Tripo/tripo.py -c 16 image2model CoreFolder-16.png --preset draft  # 形の確認（安価）
python Tools/Tripo/tripo.py -c 16 image2model CoreFolder-16.png --preset standard --model-seed 42 --orientation align_image
python Tools/Tripo/tripo.py -c 16 multiview2model --front Training/front.png --left Training/left.png --back Training/back.png
python Tools/Tripo/tripo.py -c 16 status <task_id>
python Tools/Tripo/tripo.py -c 16 convert <task_id> --format FBX
```

- `-c` は `16` / `Corefolder-16` / `NumberTales/Corefolder-16` のいずれでも可（既定シリーズは `--series NumberTales`）。
- 入力パスは `100BeautiesLab-CharacterNative/<作品>/Corefolder-<N>/` からの相対パス。URL も可。
- 成果物と台帳は同フォルダの `TripoGenerated/<日付>/<時刻>_<type>_<taskid8>/` と `TripoGenerated/jobs.jsonl` に保存されます。

## 原本との同期

### Tripo由来の中間Blenderネイティブファイル（2026-09-10 User指定）

保存先は `100BeautiesLab-CharacterNative/<作品>/<種別>-<Num>/Tripo/`。
今回の対象は `NumberTales/Corefolder-57/Tripo/` と `NumberTales/Corefolder-85/Tripo/`。
過程の比較用 `.blend` はこの中の `Iterations/` に置く。
`fit_reference_models.py` もこの配置で保存する。元の制作blendと、CLIが保存する原本 `TripoGenerated/` は移動しない。

`scripts/tripo_cli.py` と `config/tripo.yaml` の原本は Dropbox
`Claude Coworks Projectfile/Tripio AI x Claude UserFiles/tripo-3d-studio/` です。
原本が更新されたら本フォルダへ複製し直し、各ファイル冒頭に記した差分を再適用してください。

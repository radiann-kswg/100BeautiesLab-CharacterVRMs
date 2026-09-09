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

## セットアップ（Windows / PowerShell）

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

`scripts/tripo_cli.py` と `config/tripo.yaml` の原本は Dropbox
`Claude Coworks Projectfile/Tripio AI x Claude UserFiles/tripo-3d-studio/` です。
原本が更新されたら本フォルダへ複製し直し、各ファイル冒頭に記した差分を再適用してください。

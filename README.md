# 100BeautiesLab-CharacterVRMs — 「百花繚乱研究所」 公式VRMモデル

一次創作サークル **百花繚乱研究所/100BeautiesLab.** の創作キャラクター VRM モデルを管理する Unity プロジェクトです。
各キャラクターの設定データベースは [100BeautiesLab_CreationsDB](https://github.com/radiann-kswg/100BeautiesLab_CreationsDB) を参照してください。

---

## ライセンス / License

本リポジトリに含まれる VRM モデル・テクスチャ等の創作アセットは、百花繚乱研究所の一次創作作品として以下のライセンスで提供されます。

- **クリエイティブ・コモンズ 表示 - 非営利 4.0 国際（CC BY-NC 4.0）**
- **100BeautiesLab.(百花繚乱研究所) Primary Works/Creations © 2021-2026 by RadianN_kswg(ラジアン/柏木主税) is licensed under CC BY-NC 4.0**
  http://creativecommons.org/licenses/by-nc/4.0/

ライセンス全文は本リポジトリの [LICENCE](./LICENCE) を参照してください。

### ガイドライン（正本）

利用許可・二次創作の OK/NG リスト・違反行為の定義など、権利・運用上の重要情報は
**`100BeautiesLab_CreationsDB` リポジトリのガイドラインファイルが正本** です。本リポジトリのアセット利用時も必ず順守してください。

- 日本語版（正本）: [100BeautiesLab_CreationsDB/guideline.md](https://github.com/radiann-kswg/100BeautiesLab_CreationsDB/blob/main/guideline.md)
- English version: [100BeautiesLab_CreationsDB/guideline.en.md](https://github.com/radiann-kswg/100BeautiesLab_CreationsDB/blob/main/guideline.en.md)

> 各 `.vrm` ファイルに埋め込まれた VRM Meta（ライセンス情報）も併せて有効です。README と Meta の内容が異なる場合はガイドライン正本を優先してください。

This repository's creative assets (VRM models, textures, etc.) are licensed under **CC BY-NC 4.0**.
For usage permissions and derivative-work rules, see the canonical guideline files in the
[100BeautiesLab_CreationsDB](https://github.com/radiann-kswg/100BeautiesLab_CreationsDB) repository.

---

## 収録モデル

`Assets/100BeautiesLab-CharacterVRM/` 配下に作品シリーズ別で格納しています。

### ナンバーテールズ (NumberTales)

| フォルダ | VRM ファイル | サムネイル | 備考 |
| --- | --- | --- | --- |
| `NumberTales/Corefolder-4` | `vrm_corefolder4.vrm` | `vrm_corefolder4.png` | 導入済み |
| `NumberTales/Corefolder-16` | `vrm_corefolder16.vrm` | `vrm_corefolder16.png` | 導入済み |
| `NumberTales/Corefolder-20` | `vrm_corefolder20.vrm` | `vrm_corefolder20.png` | 導入済み |
| `NumberTales/Corefolder-25` | `vrm_corefolder25.vrm` | `vrm_corefolder25.png` | 導入済み |
| `NumberTales/Corefolder-22` | `VRCModel_CoreFloder-22.vrm` | — | 導入済み（サムネイル未整備） |
| `NumberTales/Corefolder-93` | `VRCModel_CoreFloder-93.vrm` | — | 導入済み（サムネイル未整備） |

各キャラクターの公式設定は [100BeautiesLab_CreationsDB](https://github.com/radiann-kswg/100BeautiesLab_CreationsDB) のデータベース（Works_NumberTales）を参照してください。

### AI 生成パイプラインからの参照（2026-08-29 新設）

`vrm_corefolder<番号>.png`（各 `Corefolder-<番号>/` 直下のサムネイル）は、
[100BeautiesLab_GeneratorsAI](https://github.com/radiann-kswg/100BeautiesLab_GeneratorsAI) の画像生成パイプラインが
**「3D 原典モデルの作風アンカー」として最優先参照に注入**します（環境変数 `NT_VRM_STYLE_REFS_DIR` に
`Assets/100BeautiesLab-CharacterVRM/NumberTales/` を指定。ファイル名 glob で解決）。

- サムネイルの **ファイル名（`vrm_corefolder<番号>.png`）と配置を変更する場合**は、GeneratorsAI 側
  （`src/utils/dataset.py` の `_collect_vrm_style_refs`）への影響を確認してください。
- 新規モデル導入時は同名規則でサムネイルを書き出すと、追加作業なしで生成参照に反映されます。

---

## 技術情報

- **Unity**: 6000.3.23f1（Unity 6）
- **VRM**: [UniVRM](https://github.com/vrm-c/UniVRM) v0.131.1（UniGLTF / VRM 0.x / VRM 1.0）

### ディレクトリ構成（抜粋）

```
Assets/
├── 100BeautiesLab-CharacterVRM/   # キャラクター VRM アセット（作品シリーズ別）
│   └── NumberTales/
│       └── Corefolder-<番号>/     # モデル本体・マテリアル・テクスチャ等
├── Scenes/                        # シーン
└── Settings/                      # レンダリング設定等
```

### 開発メモ

- `Library/` `Temp/` `Logs/` `obj/` `UserSettings/` などの生成物はコミット対象外です。
- `.meta` ファイルは Unity が管理します。アセットの追加・移動・削除時は Unity エディタ経由で行ってください。
- エージェント向けの運用ルールは [AGENTS.md](./AGENTS.md)（正典）/ [CLAUDE.md](./CLAUDE.md) を参照してください。

---

## 連絡先

利用許可の申請・違反行為の報告などは、ガイドライン記載の連絡先（[ホームページ](https://www.numbertales-radiann.net) / メール）までお願いします。

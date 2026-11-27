# 作風LoRAの試験結果 — 2026-09-09

AGENTS.md §9.1 に #4・#16・#20・#22・#25・#93 を作風・質感・モデル構造の規範として追記済み。

画像用SDXL LoRAの実学習は完了。6体の実VRMをMToonの透過・輪郭込みで撮影した24例と、57・85の生成三面図2例を使用した。
400ステップ、RTX 5060 Ti、約9分33秒。学習プロセスのGPU最大確保量8.13GiB、最大割り当て量7.44GiB。
GPU全体の使用量にはUnity等も加わる。クラウド使用・費用は0。
1120テンソルが有限値、ゼロ初期化されたLoRA上側560テンソルが非ゼロになったことを確認した。保存重みは約23.4MB。

## 三面図を条件にした比較

左はSDXL base、右は追加学習後。同じ入力画像・seed 2026・生成30ステップ・guidance 5.5・変化量0.3。LoRA強度0.8。
元の二段構成と丸い体形はおおむね残る。作風変化は控えめで、細部の線、顔、腕章の文字は安定していない。
これらは技術検証用で、確定デザインではない。

### #57

| 学習前 | 学習後 |
| --- | --- |
| ![学習前](<D:/Unity UserFile/Claude Cowork Projects/100BeautiesLab-CharacterVRMs/100BeautiesLab-CharacterNative/NumberTales/Corefolder-Training/style-training/evaluation/style-lora-v2-design-1024/57-base.png>) | ![学習後](<D:/Unity UserFile/Claude Cowork Projects/100BeautiesLab-CharacterVRMs/100BeautiesLab-CharacterNative/NumberTales/Corefolder-Training/style-training/evaluation/style-lora-v2-design-1024/57-lora.png>) |

### #85

| 学習前 | 学習後 |
| --- | --- |
| ![学習前](<D:/Unity UserFile/Claude Cowork Projects/100BeautiesLab-CharacterVRMs/100BeautiesLab-CharacterNative/NumberTales/Corefolder-Training/style-training/evaluation/style-lora-v2-design-1024/85-base.png>) | ![学習後](<D:/Unity UserFile/Claude Cowork Projects/100BeautiesLab-CharacterVRMs/100BeautiesLab-CharacterNative/NumberTales/Corefolder-Training/style-training/evaluation/style-lora-v2-design-1024/85-lora.png>) |

## 文章のみの比較と限界

512pxではキャラの繰り返しが発生。1024px・単体構図では重複は解消し、顔が規範寄りに変化したが、衣装・体形・尻尾数が対象設定と一致しない。
画像LoRAだけで57・85の正確な形状やVRM構造を再現できたとは評価しない。
三面図による形状条件を保持しながら、既存VRMのUV・透過ハイライト・MToonと共通素体に基づく実モデル調整が必要。
この画像学習処理では57・85のメッシュ・材質は更新していない。

全26例を訓練に使っている。比較に入力した57・85の三面図も訓練済みで、未知キャラへの汎化を証明する試験ではない。
損失の最初50ステップ平均0.03969、最後50ステップ平均0.03402はノイズ除去の訓練損失であり、作風一致の点数ではない。

## 再利用

- 重み: `models/style-lora-v2.safetensors`（Git LFS対象）。
- 重み・学習コード・データセットのハッシュと実測値: `result.json`。
- 入力画像とキャプションの出典: `dataset-manifest.json`。
- 原本6体の不変・見切れ・白紙チェック: `data-checks.json`。
- 撮影と再学習の手順: `README.md`。

規範6体の元VRMは不変。撮影用コピーは片付け、Unityは57・85の制作シーンに戻してある。
PC用URPには公式MToon輪郭機能を追加した。Unity Consoleのエラーは0件。

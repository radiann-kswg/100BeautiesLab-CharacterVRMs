# ムイとイズナの多視点ラフ校正（2026-11-26）

2体とも、側面の厚みは立ち絵1枚からの旧ラフより読みやすくなったよ。ムイでは襟と胸の距離、イズナではポニー・腕章・背中の尾の前後関係を照合できた。以下の図の最下段が、今回照合した制作版VRMだよ。

## #6 ムイ

![ムイの公式資料、実GLBの新旧三面、校正VRMの三面](studio-multiview-6.png)

新ラフの側面では、襟が丸い胴に沿って前へ下がり、ブローチが胸の表面に載る。現行VRMでもこの位置関係と独立した襟・ブローチを確認できた。一方、新ラフには背面の中央に頭より高く反り返る大きな房がある。公式尾図の上段は左右に分かれ、全体が左右各3本に対応する。背面の判断には公式図を採用し、制作版の6本の尾と独立した揺れ骨を維持したよ。

[制作版VRM](../../Corefolder-6/Modeling/Corefolder-6.vrm) ／ [新ラフGLB](../../Corefolder-6/TripoGenerated/studio/2026-11-26/Corefolder-6-67cc2e98-4c9e-4442-acf4-26f3f3e793ce.glb) ／ [生成見本](../../Corefolder-6/Training/StudioReference-20261126/studio-guide.webp) ／ [Studioジョブ](https://studio.tripo3d.ai/ja/workspace/generate/67cc2e98-4c9e-4442-acf4-26f3f3e793ce)

## #57 イズナ

![イズナの公式資料、実GLBの新旧三面、校正VRMの三面](studio-multiview-57.png)

旧ラフの背面を覆っていた一つの丸い塊が、新ラフでは前後に重なる房に分かれた。右側面から、ポニーの毛先が腕章にかかる位置も読める。ただし公式尾図で手前中央にある二股の先端は、新ラフでは尖った房が重なり、どの根元につながるかを特定できない。制作版には公式図由来の分岐と7本の揺れ骨があり、横からは腕章の「57」も読める。腕章と髪を個別に装着した現行版を採用したよ。

[制作版VRM](../../Corefolder-57/Modeling/Corefolder-57.vrm) ／ [新ラフGLB](../../Corefolder-57/TripoGenerated/studio/2026-11-26/Corefolder-57-a4991917-405e-4707-a27b-42c10b8f5b27.glb) ／ [生成見本](../../Corefolder-57/Training/StudioReference-20261126/studio-guide.webp) ／ [Studioジョブ](https://studio.tripo3d.ai/ja/workspace/generate/a4991917-405e-4707-a27b-42c10b8f5b27)

## 入力と照合条件

入力順は、① CreationsDB の各キャラの立ち絵1、② 規範 #16 ソロクの実VRM正面、③ 各キャラの公式尾図。規範 #16 はムイの前髪の量感とイズナの結び髪を胴と見比べるために選んだ。各キャラの指示を下のファイルに保存してあるよ。Nano Bananaで1:1の見本を1枚ずつ作り、それぞれ前・左・右・背面に展開した。3D生成はH3.5プレビューのHDモデル、形状のみ、リンク限定公開。残高は9,050から8,990、実消費は各30クレジット。[規範 #16 の入力画像](../style-training/captures/Corefolder-16/front.png) ／ [ムイの指示](../../Corefolder-6/Training/StudioReference-20261126/prompt.txt) ／ [イズナの指示](../../Corefolder-57/Training/StudioReference-20261126/prompt.txt) ／ [CLIで同じ入力を渡す手順](../../../../Tools/Tripo/README.md#規範vrmの撮影画像を添えてラフを作る)

| キャラ | 旧GLBの奥行／幅 | 新GLBの奥行／幅 | 新GLBの三角形 | 制作版VRMの三角形 | 制作版の尾／揺れる髪 |
| --- | ---: | ---: | ---: | ---: | ---: |
| ムイ | 0.412 | 0.929 | 1,955,136 | 14,568 | 6本／2房 |
| イズナ | 0.485 | 0.915 | 1,864,279 | 24,260 | 7本／3房 |

奥行／幅はGLBの全頂点を使ったZ軸幅÷X軸幅で、尾を含む全身の比率だよ。比較図の各正面・側面・背面は正投影で、モデルごとに表示サイズを合わせた。新GLBはいずれもスキンなし。番号・瞳・毛先の色、素体と装飾のウェイトは校正VRMで確認した。

## 制作版VRMの再検査

今回、2体の編集用BlendをBlenderで再読込し、VRMの構造・ウェイト・テクスチャとUnity配置版の同一性を再検査した。両方ともHumanoid 53スロット、頂点あたり最大4ウェイト、主色は1024×1024のRGBA PNGを2枚内蔵。glTF Validatorのエラーは0、従来の拡張名の形式に関する警告が各1件。下のSHA-256は既存のUnity 6000.3.23f1のPlay Mode撮影記録とも一致し、各10姿勢の記録を再集計した結果、揺れ物と左右の目の重なりは0画素だったよ。[校正版の形式検査](studio-format-checks.json) ／ [同じVRMのUnity計測記録](studio-calibration.json)

| キャラ | 検証した制作版VRMのSHA-256 | 今回保存したGLBのSHA-256 |
| --- | --- | --- |
| ムイ | `0ad2a25e1d5b64b78b31b2f8e5727623fc670cc0ab884ad9bc5b5ba33b191f95` | `0489246ec07e4c66d7134d37ed931aa7925e0f14101f1c2b345e445e12fd5194` |
| イズナ | `6610caa696828280915aeea8c626ad3d12cb71c82f23a432d663608a8ffeb95a` | `2762ad576e675ad13888fd3fd2b13f64f006ed6bdf9c020c8e516b3a42b489e7` |

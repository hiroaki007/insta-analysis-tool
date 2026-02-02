# 📸 Insta Research Dashboard (Multi-Account Analyzer)

Instagramの競合リサーチを自動化し、数時間かかる分析を「数秒」に短縮するWebアプリケーションです。

## 🌟 主な機能
- **複数アカウントの一括リサーチ**: カンマ区切りで複数のIDを同時に解析。
- **バズり投稿の自動判定**: 平均いいね数の1.5倍以上の投稿を「🔥バズり」として自動抽出。
- **ビジュアル分析**: 投稿URLだけでなく、実際のサムネイル画像を一覧表示。
- **データ可視化**: アカウントごとの平均エンゲージメントをグラフで比較。
- **データ出力**: 分析結果をCSV形式で即座にダウンロード可能。

## 🛠 使用技術
- **Language**: Python 3.12
- **Framework**: Streamlit (Web UI)
- **Library**: instagrapi, pandas, python-dotenv
- **Version Control**: Git / GitHub

## 🚀 使い方
1. リポジトリをクローン
2. `.env` ファイルにInstagramのログイン情報を設定
3. `pip install -r requirements.txt` でライブラリをインストール
4. `streamlit run app.py` で起動

## 💡 開発の背景
SNSマーケティングにおいて、競合分析は不可欠ですが、手動でのデータ収集には多大な時間がかかります。この課題を解決するため、非エンジニアの運用担当者でも直感的に「勝てる投稿」を特定できるツールとして開発しました。
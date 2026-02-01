# Instagram Research Automator

競合アカウントの投稿データを自動収集し、バズっている投稿を特定するリサーチツールです。

## 機能
- 指定した複数アカウントの最新投稿を自動取得
- pandasを用いた「バズり（平均いいねの1.5倍以上）」の自動判定
- 実行時のタイムスタンプ付きCSV出力
- Instagram APIの制限を考慮したランダム待機ロジック実装

## 技術スタック
- Python 3.13
- instagrapi (API Wrapper)
- pandas (Data Analysis)
- python-dotenv (Security)
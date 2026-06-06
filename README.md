# Market Daily Report

日経225・S&P500・BTC/USD の値動きとテクニカル指標を毎朝 8:00 JST に自動取得し、  
GitHub Pages で公開する HTML レポート生成システムです。

## ファイル構成

```
.
├── fetch_and_build.py        # データ取得 + HTML 生成
├── index.html                # 生成されたレポート（GitHub Pages で公開）
├── .github/workflows/
│   └── daily.yml             # GitHub Actions 定期実行ワークフロー
└── README.md
```

## セットアップ手順

### 1. GitHub リポジトリの作成

```bash
# ローカルで初期化
cd /path/to/myProject
git init
git add .
git commit -m "initial commit"

# GitHub CLI を使う場合（おすすめ）
gh repo create market-daily-report --public --source=. --remote=origin --push

# または GitHub Web UI でリポジトリ作成後
git remote add origin https://github.com/<YOUR_USERNAME>/market-daily-report.git
git branch -M main
git push -u origin main
```

### 2. GitHub Pages の有効化

1. GitHub のリポジトリページを開く
2. **Settings** → **Pages** を選択
3. **Source** を `Deploy from a branch` に設定
4. **Branch** を `main` / `(root)` に設定して **Save**
5. 数分後に `https://<YOUR_USERNAME>.github.io/market-daily-report/` で公開される

### 3. 初回手動実行

1. GitHub リポジトリの **Actions** タブを開く
2. 左メニューから **Daily Market Report** を選択
3. **Run workflow** ボタンをクリック → **Run workflow** で実行
4. 完了後、`index.html` がリポジトリにコミットされ Pages に反映される

### 4. ローカルでの動作確認

```bash
pip install yfinance pandas numpy requests pytz
python fetch_and_build.py
# index.html が生成されるのでブラウザで開いて確認
open index.html   # macOS
```

## 定期実行時刻の変更

`.github/workflows/daily.yml` の `cron` 行を編集します。

```yaml
on:
  schedule:
    - cron: '0 23 * * *'   # ← ここを変更
```

### cron 書式

```
┌───── 分 (0-59)
│ ┌───── 時 (0-23)  ※ UTC
│ │ ┌───── 日 (1-31)
│ │ │ ┌───── 月 (1-12)
│ │ │ │ ┌───── 曜日 (0=日, 6=土)
│ │ │ │ │
* * * * *
```

| 希望時刻 (JST) | UTC     | cron 設定         |
|---------------|---------|-------------------|
| 毎朝 7:00     | 22:00   | `0 22 * * *`      |
| 毎朝 8:00     | 23:00   | `0 23 * * *`      |
| 毎朝 9:00     | 0:00    | `0 0 * * *`       |
| 平日朝 8:00   | 23:00   | `0 23 * * 1-5`    |

> **Note:** GitHub Actions のスケジュールは混雑時に数分〜数十分遅延することがあります。

## テクニカル指標一覧

| 指標 | 計算方法 | 強気サイン | 弱気サイン |
|------|---------|-----------|-----------|
| RSI (14日) | Wilder 平滑化 | ≤ 30（過売り） | ≥ 70（過買い） |
| 移動平均 | MA25 / MA75 | 価格 > MA | 価格 < MA |
| MACD | EMA12 − EMA26, シグナル EMA9 | ゴールデンクロス | デッドクロス |
| ボリンジャーバンド | 20日 ±2σ | 下限近接 | 上限近接 |
| 出来高 | 直近 20 日平均比 | 1.5 倍超 | 0.5 倍未満 |

## データソース

- **株価（日経225・S&P500）**: [yfinance](https://github.com/ranaroussi/yfinance) (Yahoo Finance)  
- **BTC/USD**: [CoinGecko API](https://www.coingecko.com/en/api) (無料・APIキー不要)

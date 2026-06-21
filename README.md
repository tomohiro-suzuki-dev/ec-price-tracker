# ec-price-tracker

Amazon・楽天ブックスの価格を毎日監視し、変動をDiscordに通知するツールです。

## 機能

- 複数ECサイト（Amazon/楽天ブックス）の価格を同時取得
- 前日との価格差・変動率をDiscordに通知
- 値下がりは緑、値上がりは赤でカラー表示
- GitHub Actionsで毎日自動実行

## 技術スタック

- Python 3.11
- Playwright（ブラウザ自動化・価格スクレイピング）
- GitHub Actions（日次定期実行・状態キャッシュ）
- Discord Webhook（通知）

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 監視商品の設定

`config.yml` を編集して監視したい商品とURLを追加してください。

```yaml
products:
  - name: 商品名
    urls:
      - site: Amazon
        url: https://www.amazon.co.jp/dp/XXXXXXXXXX
      - site: 楽天ブックス
        url: https://books.rakuten.co.jp/rb/XXXXXXX/
```

### 3. Discord Webhookの設定

GitHubリポジトリの `Settings > Secrets and variables > Actions` に以下を追加：

| Secret名 | 値 |
|---|---|
| `DISCORD_WEBHOOK_URL` | DiscordチャンネルのWebhook URL |

### 4. ローカルでの実行

```bash
export DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
python tracker.py
```

## GitHub Actions

`.github/workflows/tracker.yml` により毎日0時（UTC）に自動実行されます。
前回実行時の価格は `actions/cache` で管理されます。

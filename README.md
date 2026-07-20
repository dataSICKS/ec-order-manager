# ec-order-manager

ECforce受注のバックオフィス運用ツール。FastAPI + Jinja2 のダッシュボードで、**住所不備・与信落ち・重複注文・テスト受注**を検知して一覧化し、担当者がワンクリックで「住所修正＋再与信」「再オーソリ」「決済キャンセル」「テスト受注の後始末」を実行できる。あわせて出荷CSVの出力→Google Drive アップロード→Chatwork 通知、および APScheduler による定期チェック（重複検知の Slack 通知）を担う。

- 対象EC基盤: **ECforce**（REST API `Token token='...'` 認証）
- 本番 URL（想定）: https://ec-order-manager.replit.app （重複検知の Slack 通知に埋め込まれるリンク）
- ホスティング: Replit（`.replit` の `run` で uvicorn 起動）

## ドキュメント（機能別）

| ファイル | 内容 |
|---|---|
| [DESIGN.md](DESIGN.md) | **設計** — 目的・背景、アーキ/データフロー(ASCII)、機能、技術スタック、データモデル概要、主要な設計判断(why) |
| [CODE.md](CODE.md) | **コード** — ディレクトリ構成、主要モジュール/ルート解説、拡張・変更手順（ステップ）、コピペ用テンプレート（実コード） |
| [UI.md](UI.md) | **画面** — デザイントークン、レイアウト/ナビ、画面一覧（画面×役割×UI）、コンポーネント、UX方針、レスポンシブ |
| [OPERATIONS.md](OPERATIONS.md) | **運用** — セットアップ、環境変数表、デプロイ/実行、cron(APScheduler)、運用手順、チェックリスト、トラブルシューティング |
| [DATA.md](DATA.md) | **データ** — SQLite テーブル定義、ECforce API のクエリ/エンドポイント一覧、重複判定ロジック、指標定義、データソースと更新頻度 |

## クイックスタート

```bash
pip install -r requirements.txt

# 環境変数を設定（最低限 ECFORCE_BASE_URL / ECFORCE_API_TOKEN。詳細は OPERATIONS.md）
export ECFORCE_BASE_URL="https://<shop>.ec-force.com"
export ECFORCE_API_TOKEN="<token>"

uvicorn main:app --host 0.0.0.0 --port 8080
# ブラウザで http://localhost:8080
```

- SQLite（`ec_manager.db`）は起動時に自動生成されるため事前準備不要。
- ECforce 未接続でもダッシュボードは開く（統計は 0 表示＋接続エラー文言）。

> 注意: 本ツールの操作（再与信・決済キャンセル・定期購入削除）は**本番 ECforce に対する破壊的操作**を含む。必ず [OPERATIONS.md](OPERATIONS.md) のチェックリストを確認のうえ実行すること。

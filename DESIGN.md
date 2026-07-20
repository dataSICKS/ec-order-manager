# DESIGN — ec-order-manager 設計

## 目的・背景

ECforce で受注を運用する際、そのまま出荷に進めてはいけない「要対応受注」が日々発生する。

- **住所不備**: 配送先住所が不完全で出荷できない。住所を直してから再与信が必要。
- **与信落ち（オーソリエラー）**: カード与信が通らず売上確定できない。再オーソリで復旧を試みる。
- **重複注文**: 同一顧客が同一商品を短時間に二重注文。一方の決済をキャンセルする必要がある。
- **テスト受注**: 検証目的の注文が本番に混入。決済キャンセル＋（あれば）定期購入の解約・削除で後始末する。

ECforce の管理画面だけでこれらを都度捌くのは手間が大きく、対応漏れも起きやすい。本ツールは、これら4カテゴリを**1画面で検知・集計し、対応をワンクリック化**する。加えて、

- 出荷対象（`shipment_status=pending`）の**出荷CSVを出力 → Google Drive にアップロード → Chatwork で共有**するバッチ、
- **定期チェック**（重複注文/与信落ち）を APScheduler で自動実行し、重複検知時に Slack 通知、

を備えることで、日次の受注オペレーションを集約する。

## アーキテクチャ（ASCII）

```
                    ┌───────────────────────────────────────────────┐
   担当者ブラウザ ──▶│  FastAPI (main.py)  +  Jinja2 テンプレート       │
   （Bootstrap 5）   │                                                 │
                    │  GET  /                 ダッシュボード           │
                    │  routers/orders.py      住所/与信/重複/テスト    │
                    │  routers/batches.py     出荷CSV/テスト一括処理   │
                    └───────┬───────────────────────────┬─────────────┘
                            │                           │
              ┌─────────────▼──────────┐     ┌──────────▼───────────────┐
              │ services/ecforce.py     │     │ SQLite (database.py)      │
              │  EcforceClient          │     │  job_logs                 │
              │  REST: /orders.json 等   │     │  processed_orders         │
              └─────────────┬──────────┘     └───────────────────────────┘
                            │
                 ┌──────────▼───────────┐
                 │  ECforce REST API     │   Authorization: Token token='...'
                 └───────────────────────┘

  APScheduler (scheduler.py) ── BackgroundScheduler(Asia/Tokyo)
     ├─ 30分ごと: check_duplicates_job ──▶ EcforceClient.get_duplicate_orders()
     │                                    重複ありなら services/slack_service.post_message()
     └─ 1時間ごと: check_credit_failures_job ─▶ EcforceClient.get_credit_failure_orders()

  出荷CSVバッチ (routers/batches.py: /export-shipping-csv)
     EcforceClient.export_shipping_csv()  ─▶  services/drive_service.upload_csv() (Google Drive)
                                          ─▶  services/chatwork_service.post_message() (Chatwork)
```

## データフロー

### 1. ダッシュボード表示（GET /）
1. `main.py` の `dashboard` が `EcforceClient().get_dashboard_stats()` を呼ぶ。
2. `get_dashboard_stats` は住所不備/与信落ち/テスト受注/重複の各件数を ECforce API から集計。
3. 例外時は全カテゴリ 0 ＋ `error` メッセージを返し、画面に警告バナー表示（アプリは落ちない）。

### 2. 個別対応（例: 住所不備の修正）
1. `GET /orders/address-errors` → `EcforceClient.get_address_error_orders()` で一覧取得しカード表示。
2. フォーム送信 `POST /orders/address-errors/{order_id}/fix` で
   `update_address` → `re_authorize` → `add_inquiry_history`（問い合わせ履歴に記録）を順に実行。
3. `processed_orders` に監査ログ（`action="fix_address"`）を保存し、一覧へ 303 リダイレクト。

### 3. 出荷CSVバッチ（POST /batches/export-shipping-csv）
1. `job_logs` に `running` を記録。
2. `EcforceClient.export_shipping_csv()`（`format=id2` / `shipment_status=pending`）で CSV バイト列取得。
3. `drive_service.upload_csv()` で Drive にアップロードし `webViewLink` 取得。
4. `chatwork_service.post_message()` でファイル名＋リンクを通知。
5. `job_logs` を `success`/`error` に更新。

### 4. 定期チェック（APScheduler）
- 30分ごと `check_duplicates_job`: 重複を検知したら Slack に上位5件＋一覧 URL を通知。
- 1時間ごと `check_credit_failures_job`: 件数を `job_logs` に記録（通知はしない）。

## 機能一覧

| 機能 | エントリ | 実処理 | 破壊的操作 |
|---|---|---|---|
| ダッシュボード | `GET /` | 4カテゴリ件数集計 | なし |
| 住所不備一覧・修正 | `GET/POST /orders/address-errors[...]` | 住所更新＋再与信＋履歴 | あり（本番更新・与信） |
| 与信落ち一覧・再オーソリ | `GET/POST /orders/credit-failures[...]` | 再オーソリ＋履歴 | あり（再与信） |
| 重複注文一覧・キャンセル | `GET/POST /orders/duplicates[...]` | 決済キャンセル＋履歴 | あり（決済取消） |
| テスト受注一覧・後始末 | `GET/POST /orders/test-orders[...]` | 決済キャンセル＋定期解約/削除 | あり（決済取消・定期削除） |
| バッチ画面・実行ログ | `GET /batches/` | `job_logs` 直近50件表示 | なし |
| 出荷CSV出力バッチ | `POST /batches/export-shipping-csv` | CSV→Drive→Chatwork | なし（読み取り＋外部連携） |
| テスト受注一括処理 | `POST /batches/process-test-orders` | 全テスト受注の決済キャンセル | あり（決済取消） |
| 定期: 重複チェック | APScheduler 30分 | 検知時 Slack 通知 | なし |
| 定期: 与信落ちチェック | APScheduler 1時間 | 件数ログ | なし |

## ロール / アクセス制御

- **認証・認可は未実装**。アプリ自体にログイン機構はなく、URL を知る全員が操作可能。
- 実質的なアクセス制御は**ホスティング側（Replit のURL秘匿等）に依存**。破壊的操作を含むため、公開範囲の管理が前提。
- 監査の代替として `processed_orders`（誰が、はないが「いつ・どの注文に・何をしたか」）を保持。

## 技術スタック

| 種別 | 採用 | 備考 |
|---|---|---|
| 言語 | Python 3（Replit nix `stable-23_11`） | |
| Webフレームワーク | FastAPI | `main.py` に `lifespan` で起動処理 |
| ASGI サーバ | uvicorn[standard] | port 8080 |
| テンプレート | Jinja2 | `templates/` |
| CSS/UI | Bootstrap 5.3 + Bootstrap Icons 1.11（CDN） | ビルド不要 |
| ORM / DB | SQLAlchemy + **SQLite**（`ec_manager.db`） | ローカルファイルDB |
| スケジューラ | APScheduler（BackgroundScheduler, Asia/Tokyo） | |
| 外部API | ECforce REST / Google Drive API / Slack API / Chatwork API | |
| HTTP | requests | |
| その他 | pandas, python-multipart（フォーム受信） | pandas は現状未使用 |

## データモデル概要

SQLite に監査・ログ用の2テーブルのみ（受注実データは ECforce 側が正）。

- **`job_logs`** … バッチ/定期タスクの実行ログ（`job_type` / `status` = running·success·error / `message` / `created_at`）。
- **`processed_orders`** … 手動対応の監査ログ（`order_id` / `action` / `note` / `processed_at`）。

詳細な列定義・制約・ECforce API のクエリは [DATA.md](DATA.md) を参照。

## 主要な設計判断（why）

- **受注データは持たず ECforce をSSoTにした**: 二重管理を避けるため。SQLite は「実行ログ」と「対応履歴」だけに限定。
- **DB は SQLite**: 監査ログ用途で十分・依存を最小化。ただし Replit の再デプロイ/コンテナ再作成でファイルが消える可能性がある（永続性は保証されない）→ 重要ログは Slack/Chatwork/ECforce 問い合わせ履歴側にも残す設計。
- **例外時もダッシュボードを落とさない**: `get_dashboard_stats` と `GET /` の二重 try/except で、ECforce 障害時でも画面を開けるようにした（運用中の完全停止を避ける）。
- **`add_inquiry_history` で ECforce 側に痕跡を残す**: 対応内容を ECforce の問い合わせ履歴にも書き込み、管理画面だけを見る他メンバーにも状況が伝わるようにした。
- **通知先を用途で分離**: 重複検知の即時アラートは **Slack**、出荷CSVの配布は **Chatwork**（メンション対応）と、既存の運用チャネルに合わせて分けている。
- **スケジューラはアプリ内蔵（APScheduler）**: 外部 cron を用意せず、単一プロセスで完結させる（Replit 常駐前提）。

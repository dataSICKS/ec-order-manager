# DATA — ec-order-manager データ定義

受注の実データは **ECforce（SSoT）** にあり、本アプリの SQLite（`ec_manager.db`）は**実行ログ・対応履歴のみ**を保持する。

## データソースと更新頻度

| データ | ソース | 取得/更新タイミング | 保存先 |
|---|---|---|---|
| 受注（住所不備/与信落ち/重複/テスト/出荷待ち） | ECforce REST `/orders.json` | 画面表示ごと（オンデマンド）＋定期タスク | 保存しない（都度取得） |
| 出荷CSV | ECforce `/orders/export.csv` | バッチ実行時 | Google Drive |
| バッチ/定期タスクの実行結果 | 本アプリ | 実行のたびに INSERT/UPDATE | SQLite `job_logs` |
| 手動対応の監査 | 本アプリ | 対応POSTのたびに INSERT | SQLite `processed_orders` |

- 定期取得: 重複=30分ごと、与信落ち=1時間ごと（[OPERATIONS.md](OPERATIONS.md) 参照）。

## SQLite テーブル定義

### `job_logs` — バッチ/定期タスクの実行ログ

| 列 | 型 | 説明 |
|---|---|---|
| `id` | Integer, PK, index | 主キー |
| `job_type` | String | ジョブ種別（`check_duplicates` / `check_credit_failures` / `export_shipping_csv` / `process_test_orders` 等） |
| `status` | String | `running` / `success` / `error` |
| `message` | Text | 結果メッセージ（件数やエラー内容） |
| `created_at` | DateTime | 既定 `datetime.now`（アプリ生成） |

- 生成時は `running` で INSERT し、処理完了後に同レコードを `success`/`error` に UPDATE する（`created_at` は生成時刻のまま）。
- `/batches/` 画面は `created_at` 降順・上限50件で表示。

### `processed_orders` — 手動対応の監査ログ

| 列 | 型 | 説明 |
|---|---|---|
| `id` | Integer, PK | 主キー |
| `order_id` | String, index | ECforce の注文ID |
| `action` | String | `fix_address` / `reauth` / `cancel_duplicate` / `test_order_cleanup` |
| `note` | Text | 補足（住所修正時は修正後住所など） |
| `processed_at` | DateTime | 既定 `datetime.now` |

> 制約について: いずれのテーブルも SQLAlchemy 定義上に UNIQUE/NOT NULL/CHECK/FK の明示はない（`id` の PK と一部 `index` のみ）。同一注文への複数回対応は追記として蓄積される。

### DDL（SQLAlchemy が `create_all` で生成する等価SQL）

```sql
CREATE TABLE job_logs (
    id INTEGER NOT NULL,
    job_type VARCHAR,
    status VARCHAR,
    message TEXT,
    created_at DATETIME,
    PRIMARY KEY (id)
);
CREATE INDEX ix_job_logs_id ON job_logs (id);

CREATE TABLE processed_orders (
    id INTEGER NOT NULL,
    order_id VARCHAR,
    action VARCHAR,
    note TEXT,
    processed_at DATETIME,
    PRIMARY KEY (id)
);
CREATE INDEX ix_processed_orders_order_id ON processed_orders (order_id);
```

## ECforce REST API 一覧（`EcforceClient`）

- ベースURL: `ECFORCE_BASE_URL`（末尾スラッシュ除去）。認証: `Authorization: Token token='<ECFORCE_API_TOKEN>'`。
- 全レスポンスは `raise_for_status()` でエラー時に例外。

### 取得系

| メソッド | HTTP | エンドポイント | クエリ | 返り値 |
|---|---|---|---|---|
| `get_orders(params)` | GET | `/orders.json` | 任意 | JSON全体 |
| `get_order(id)` | GET | `/orders/{id}.json` | — | JSON |
| `get_address_error_orders()` | GET | `/orders.json` | `q[payment_status_eq]=address_error`, `per=50` | `orders[]` |
| `get_credit_failure_orders()` | GET | `/orders.json` | `q[payment_status_eq]=authorization_error`, `per=50` | `orders[]` |
| `get_test_orders()` | GET | `/orders.json` | `q[test_order_eq]=true`, `q[status_not_eq]=cancelled`, `per=50` | `orders[]` |
| `get_duplicate_orders()` | GET | `/orders.json` | `q[created_at_gteq]=(24h前)`, `q[status_not_eq]=cancelled`, `per=200` | 重複のみ（下記ロジック） |
| `get_pending_shipment_orders()` | GET | `/orders.json` | `q[shipment_status_eq]=pending`, `q[status_eq]=confirmed`, `per=200` | `orders[]` |
| `get_dashboard_stats()` | — | 上記4件を集計 | — | `{address_errors, credit_failures, test_orders, duplicates}`（例外時 `error` 付） |
| `export_shipping_csv()` | GET | `/orders/export.csv` | `format=id2`, `q[shipment_status_eq]=pending` | CSV バイト列 |

### 操作系（破壊的）

| メソッド | HTTP | エンドポイント | ボディ |
|---|---|---|---|
| `cancel_payment(id)` | POST | `/orders/{id}/payment_cancel.json` | — |
| `re_authorize(id)` | POST | `/orders/{id}/re_authorization.json` | — |
| `update_address(id, addr)` | PATCH | `/orders/{id}.json` | `{"order": {"shipping_address_attributes": addr}}` |
| `add_inquiry_history(id, msg)` | POST | `/orders/{id}/inquiry_histories.json` | `{"inquiry_history": {"body": msg}}` |
| `cancel_subscription(sid)` | PATCH | `/subscriptions/{sid}.json` | `{"subscription": {"status": "cancel"}}` |
| `delete_subscription(sid)` | DELETE | `/subscriptions/{sid}.json` | — |
| `mark_as_shipped(id, tracking, company)` | PATCH | `/orders/{id}.json` | `{"order": {"shipment_status": "shipped", "tracking_number": ..., "shipping_company": ...}}`（現状ルータ未使用） |

> 注意: `q[...]` の値（`address_error` / `authorization_error` / `cancelled` / `confirmed` / `pending` / `format=id2` 等）はショップの設定に依存する。実データと合わない場合は一覧が空になるため、`services/ecforce.py` の該当値を調整する。

## 指標・集計定義

### ダッシュボード4指標（`get_dashboard_stats`）

| 指標 | 定義（ECforceクエリ） |
|---|---|
| 住所不備 `address_errors` | `payment_status = address_error` の件数（最大50） |
| 与信落ち `credit_failures` | `payment_status = authorization_error` の件数（最大50） |
| テスト受注 `test_orders` | `test_order = true` かつ `status ≠ cancelled` の件数（最大50） |
| 重複注文 `duplicates` | 下記「重複判定」で抽出された件数 |

- いずれも `per` 上限までのページ内件数（ページネーション未対応）。件数が上限を超える運用では過小表示になりうる。

### 重複判定ロジック（`get_duplicate_orders`）

1. 直近24時間（`created_at >= now-1day`）かつ未キャンセルの注文を最大200件取得。
2. 各注文の **キー = `(customer_id, sorted(line_items[].variant_id))`** を計算。
3. 同一キーが2件以上あれば、その注文群を「重複」として返す（初回出現分も含めて追加）。

```python
seen = {}
duplicates = []
for order in orders:
    customer_id = order.get("customer_id")
    items = order.get("line_items", [])
    product_key = tuple(sorted([str(item.get("variant_id", "")) for item in items]))
    key = (customer_id, product_key)
    if key in seen:
        if seen[key] not in duplicates:
            duplicates.append(seen[key])
        duplicates.append(order)
    else:
        seen[key] = order
```

- 判定は「同じ顧客が同じ商品構成を短時間に複数注文」。数量差・金額差は考慮しない。

## 画面が参照する受注フィールド（テンプレート由来）

一覧テンプレートが `order` オブジェクトに期待するキー（ECforce レスポンス依存、存在しなければ空表示）:

`id` / `code` / `created_at` / `customer_last_name` / `customer_first_name` / `email` / `shipping_address` / `total_price` / `line_items[].name` / `line_items[].variant_id` / `customer_id` / `subscription_id`。

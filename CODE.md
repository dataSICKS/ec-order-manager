# CODE — ec-order-manager 実装ガイド

## ディレクトリ構成

```
ec-order-manager/
├── main.py                # FastAPIエントリポイント（lifespan/ルータ登録/ダッシュボード）
├── database.py            # SQLAlchemy: engine/Session/モデル(JobLog, ProcessedOrder)/init_db
├── scheduler.py           # APScheduler: 重複チェック30分・与信落ちチェック1時間
├── requirements.txt       # 依存パッケージ
├── .replit                # Replit 起動設定（run = uvicorn ...）
├── routers/
│   ├── __init__.py        # 空
│   ├── orders.py          # /orders 配下: 住所不備/与信落ち/重複/テスト受注
│   └── batches.py         # /batches 配下: 画面・出荷CSV・テスト受注一括
├── services/
│   ├── __init__.py        # 空
│   ├── ecforce.py         # EcforceClient（ECforce REST ラッパ）
│   ├── slack_service.py   # Slack chat.postMessage
│   ├── chatwork_service.py# Chatwork rooms/{id}/messages（メンション対応）
│   └── drive_service.py   # Google Drive アップロード/一覧/DL
├── templates/             # Jinja2（Bootstrap 5）
│   ├── base.html          # 共通レイアウト＋サイドバー
│   ├── index.html         # ダッシュボード
│   ├── address_errors.html
│   ├── credit_failures.html
│   ├── duplicates.html
│   ├── test_orders.html
│   └── batches.html
└── static/                # 空（現状 CSS/JS は CDN のため未使用）
```

> 補足: 旧 README には `models.py` の記載があったが**存在しない**。モデルは `database.py` に定義されている。

## 主要モジュール解説

### `main.py`
- `lifespan` で起動時に `init_db()`（テーブル作成）と `start_scheduler()`（定期タスク開始）を実行。
- ルータ登録: `orders.router`（prefix `/orders`）、`batches.router`（prefix `/batches`）。
- `GET /`（`response_class=HTMLResponse`）: `EcforceClient().get_dashboard_stats()` を呼び `index.html` を返す。ECforce 例外時は全件数 0 ＋ `error` を渡す。
- 直接実行時は `uvicorn.run("main:app", host="0.0.0.0", port=8080)`。

### `database.py`
- `SQLALCHEMY_DATABASE_URL = "sqlite:///./ec_manager.db"`（`check_same_thread=False`）。
- モデル: `JobLog`（`job_logs`）、`ProcessedOrder`（`processed_orders`）。列定義は [DATA.md](DATA.md)。
- `init_db()`: `Base.metadata.create_all`。`get_db()`: FastAPI 依存性注入用のセッションジェネレータ。

### `scheduler.py`
- `scheduler = BackgroundScheduler(timezone="Asia/Tokyo")`。
- `check_duplicates_job`（30分間隔, id=`check_duplicates`）: 重複取得 → あれば Slack 通知（上位5件＋一覧URL）→ `job_logs` 更新。
- `check_credit_failures_job`（1時間間隔, id=`check_credit_failures`）: 件数を `job_logs` に記録。
- `start_scheduler()` でジョブ登録＋ `scheduler.start()`。

### `routers/orders.py`（prefix `/orders`）

| メソッド・パス | フォーム項目 | 実処理 | 監査 action |
|---|---|---|---|
| `GET /address-errors` | — | 一覧（カード） | — |
| `POST /address-errors/{order_id}/fix` | last_name, first_name, zip_code, prefecture, city, address1, address2(任意) | `update_address`→`re_authorize`→`add_inquiry_history` | `fix_address` |
| `GET /credit-failures` | — | 一覧（テーブル） | — |
| `POST /credit-failures/{order_id}/reauth` | — | `re_authorize`→`add_inquiry_history` | `reauth` |
| `GET /duplicates` | — | 一覧（テーブル） | — |
| `POST /duplicates/{order_id}/cancel` | — | `cancel_payment`→`add_inquiry_history` | `cancel_duplicate` |
| `GET /test-orders` | — | 一覧（テーブル） | — |
| `POST /test-orders/{order_id}/process` | subscription_id(任意) | `cancel_payment`→（あれば）`cancel_subscription`→`delete_subscription` | `test_order_cleanup` |

- 全 POST は成功後 `RedirectResponse(status_code=303)` で対応する一覧に戻る（PRGパターン）。

### `routers/batches.py`（prefix `/batches`）
- `GET /`: `job_logs` を `created_at` 降順・上限50件で表示。
- `POST /export-shipping-csv`: `export_shipping_csv`→`upload_csv`→ Chatwork 通知。`job_logs` に開始→結果を記録。ファイル名は `出荷依頼_{YYYYMMDD}.csv`。
- `POST /process-test-orders`: `get_test_orders` の各件に `cancel_payment` を実行し件数を `job_logs` に記録（定期購入の解約・削除は行わない点が個別処理との差）。

### `services/ecforce.py` — `EcforceClient`
- 初期化で `ECFORCE_BASE_URL`（末尾スラッシュ除去）と `ECFORCE_API_TOKEN` を環境変数から取得。ヘッダは `Authorization: Token token='<token>'`。
- 低レベル: `_get/_post/_patch/_delete`（いずれも `raise_for_status()`）。
- 取得系/操作系メソッドとエンドポイントの対応表は [DATA.md](DATA.md) を参照。
- **重複判定**（`get_duplicate_orders`）: 直近24時間・未キャンセルの注文を最大200件取得し、`(customer_id, sorted(variant_id...))` をキーに重複を抽出。

### `services/slack_service.py`
- `chat.postMessage`（Bearer `SLACK_BOT_TOKEN`、`channel`=引数or`SLACK_CHANNEL_ID`）。`ok=false` 時は例外送出。

### `services/chatwork_service.py`
- `POST /v2/rooms/{room_id}/messages`（`X-ChatWorkToken`）。`CHATWORK_MENTION_IDS`（カンマ区切り）から `[To:id]` を先頭に付与。

### `services/drive_service.py`
- サービスアカウント（`GOOGLE_CREDENTIALS_JSON` を JSON パース）で Drive v3 クライアント生成、スコープ `.../auth/drive`。
- `upload_csv(csv_content, filename)`: `GOOGLE_DRIVE_FOLDER_ID` 配下に作成し `webViewLink` を返す。
- 他に `list_files` / `download_file` を提供（現状ルータからは未使用）。

## 拡張・変更手順

### A. 新しい「要対応カテゴリ」画面を追加する
1. `services/ecforce.py` に取得メソッドを追加（例）。
   ```python
   def get_on_hold_orders(self):
       result = self._get("/orders.json", {"q[status_eq]": "on_hold", "per": 50})
       return result.get("orders", [])
   ```
2. `templates/` に一覧テンプレートを追加（既存 `credit_failures.html` を複製し `active`/見出し/フォーム action を変更）。
3. `routers/orders.py` に `GET`（一覧）と `POST`（操作）を追加。操作後は監査ログを残す。
   ```python
   @router.get("/on-hold", response_class=HTMLResponse)
   async def on_hold(request: Request):
       orders = EcforceClient().get_on_hold_orders()
       return templates.TemplateResponse("on_hold.html", {"request": request, "orders": orders})

   @router.post("/on-hold/{order_id}/release")
   async def release(order_id: str, db: Session = Depends(get_db)):
       client = EcforceClient()
       client.re_authorize(order_id)  # 実処理に置換
       client.add_inquiry_history(order_id, "保留解除を実施しました。")
       db.add(ProcessedOrder(order_id=order_id, action="release_hold"))
       db.commit()
       return RedirectResponse("/orders/on-hold", status_code=303)
   ```
4. `templates/base.html` のサイドバーに `nav-item` を追加（`active == 'on_hold'` 判定と `set active` をテンプレートに）。
5. ダッシュボードに件数を出す場合は `get_dashboard_stats` に集計を追加し、`index.html` にカードを追加。

### B. 定期タスクを追加する
1. `scheduler.py` にジョブ関数を定義（`job_logs` に running→success/error を記録するのが定型）。
   ```python
   def check_pending_shipment_job():
       db = SessionLocal()
       log = JobLog(job_type="check_pending_shipment", status="running", message="出荷待ちチェック開始")
       db.add(log); db.commit()
       try:
           from services.ecforce import EcforceClient
           n = len(EcforceClient().get_pending_shipment_orders())
           log.status = "success"; log.message = f"出荷待ち {n}件"
       except Exception as e:
           log.status = "error"; log.message = f"エラー: {e}"
       db.commit(); db.close()
   ```
2. `start_scheduler()` に登録。
   ```python
   scheduler.add_job(check_pending_shipment_job, "interval", hours=2, id="check_pending_shipment")
   ```
3. `templates/batches.html` の「自動実行スケジュール」リストに1行追記（UIは自動反映されないため手動）。

### C. 通知先チャネルを変更・追加する
- Slack/Chatwork は環境変数で宛先を切替可能（`SLACK_CHANNEL_ID` / `CHATWORK_ROOM_ID`）。
- コードで宛先を上書きする場合は `post_message(text, channel=...)` / `post_message(text, room_id=...)` に引数を渡す。

### D. 新しいバッチ（手動実行）を追加する
1. `routers/batches.py` に `POST` を追加し、`job_logs` へ running→success/error を記録。
2. `templates/batches.html`（および必要なら `index.html` のクイックアクション）に `<form method="post">` ＋ボタンを追加。

## コピペ用テンプレート

### 一覧テンプレート（テーブル型・実コード雛形）
`credit_failures.html` を基にしたテンプレート。`{見出し}` `{active}` `{action}` を差し替える。
```html
{% extends "base.html" %}
{% set active = "on_hold" %}
{% block content %}
<h4 class="mb-4"><i class="bi bi-pause-circle me-2"></i>保留中（{{ orders|length }}件）</h4>

{% if orders %}
<div class="table-responsive">
  <table class="table table-hover bg-white shadow-sm rounded">
    <thead class="table-light">
      <tr><th>注文番号</th><th>顧客名</th><th>金額</th><th>注文日</th><th>操作</th></tr>
    </thead>
    <tbody>
      {% for order in orders %}
      <tr>
        <td>#{{ order.code or order.id }}</td>
        <td>{{ order.customer_last_name or '' }} {{ order.customer_first_name or '' }}</td>
        <td>¥{{ "{:,}".format(order.total_price|int) if order.total_price else '-' }}</td>
        <td>{{ order.created_at or '' }}</td>
        <td>
          <form action="/orders/on-hold/{{ order.id }}/release" method="post" class="d-inline">
            <button class="btn btn-sm btn-primary">解除</button>
          </form>
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% else %}
<div class="alert alert-success"><i class="bi bi-check-circle me-2"></i>対象の注文はありません。</div>
{% endif %}
{% endblock %}
```

### ECforce 取得メソッド（雛形）
```python
def get_xxx_orders(self):
    result = self._get("/orders.json", {
        "q[<attr>_eq]": "<value>",
        "per": 50,
    })
    return result.get("orders", [])
```

### 監査ログ付き POST ハンドラ（雛形）
```python
@router.post("/xxx/{order_id}/do")
async def do_xxx(order_id: str, db: Session = Depends(get_db)):
    client = EcforceClient()
    client.<action>(order_id)                 # 実処理
    client.add_inquiry_history(order_id, "<対応内容>")  # ECforce側に痕跡
    db.add(ProcessedOrder(order_id=order_id, action="<action_name>"))
    db.commit()
    return RedirectResponse("/orders/xxx", status_code=303)
```

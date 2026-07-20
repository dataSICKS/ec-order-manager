# OPERATIONS — ec-order-manager 運用

## 前提

- Python 3（Replit: nix channel `stable-23_11`）。
- ECforce の API トークン（REST。`Authorization: Token token='...'`）。
- 出荷CSVバッチを使う場合: Google サービスアカウント JSON ＋ 共有済み Drive フォルダ、Chatwork API トークン。
- 定期チェックの Slack 通知を使う場合: Slack Bot トークン ＋ 通知先チャンネル。

## 環境変数

すべて OS 環境変数（`os.environ.get`）から読み込む。**値そのものはここに書かない**。Replit では Secrets、ローカルでは `export` で設定する（`.env` を使う場合は起動前に読み込む仕組みを別途用意）。

| 変数名 | 必須 | 用途 | 参照元 |
|---|---|---|---|
| `ECFORCE_BASE_URL` | ◎ | ECforce の API ベースURL（末尾スラッシュは自動除去） | `services/ecforce.py` |
| `ECFORCE_API_TOKEN` | ◎ | ECforce API トークン | `services/ecforce.py` |
| `SLACK_BOT_TOKEN` | 重複通知使用時 | Slack `chat.postMessage` の Bearer トークン | `services/slack_service.py` |
| `SLACK_CHANNEL_ID` | 重複通知使用時 | 通知先チャンネルID | `services/slack_service.py` |
| `CHATWORK_API_TOKEN` | 出荷CSV使用時 | Chatwork API トークン | `services/chatwork_service.py` |
| `CHATWORK_ROOM_ID` | 出荷CSV使用時 | 投稿先ルームID | `services/chatwork_service.py` |
| `CHATWORK_MENTION_IDS` | 任意 | メンション対象のカンマ区切りID（`[To:id]` を先頭付与） | `services/chatwork_service.py` |
| `GOOGLE_CREDENTIALS_JSON` | 出荷CSV使用時 | サービスアカウント鍵JSON（**文字列そのもの**をパース） | `services/drive_service.py` |
| `GOOGLE_DRIVE_FOLDER_ID` | 出荷CSV使用時 | アップロード先フォルダID（要事前共有） | `services/drive_service.py` |

> 未設定でも起動はできる（`get` の既定値は空文字）。ただし ECforce 未設定ではダッシュボード統計が 0 ＋接続エラー表示になり、各連携も失敗する。

## セットアップ（ローカル）

```bash
pip install -r requirements.txt

export ECFORCE_BASE_URL="https://<shop>.ec-force.com"
export ECFORCE_API_TOKEN="<token>"
# 必要に応じて Slack / Chatwork / Google の変数も export

uvicorn main:app --host 0.0.0.0 --port 8080
# http://localhost:8080
```

- 起動時に `init_db()` が `ec_manager.db`（SQLite）を自動生成。事前マイグレーション不要。
- 起動と同時に APScheduler が定期タスクを開始する。

## デプロイ / 実行（Replit）

- `.replit` の `run` に起動コマンドが定義済み:
  ```
  run = "uvicorn main:app --host 0.0.0.0 --port 8080"
  ```
- Secrets に上表の環境変数を登録して Run するだけ。
- 公開URL（想定）: `https://ec-order-manager.replit.app`（重複通知 Slack メッセージ内の一覧リンクに使用）。
- 破壊的操作を含むため、**URLの公開範囲を限定**すること（アプリ内認証は未実装）。

> データ永続性の注意: `ec_manager.db` はコンテナのファイルシステム上。Replit の再デプロイ/コンテナ再生成でログが失われる可能性がある。重要な記録は ECforce の問い合わせ履歴・Slack・Chatwork 側にも残す運用とする。

## スケジュール（APScheduler / 外部cronではない）

`scheduler.py` の `BackgroundScheduler(timezone="Asia/Tokyo")` にアプリ内で登録。**アプリが起動している間のみ動作**する。

| ジョブID | 間隔 | 処理 | 通知 |
|---|---|---|---|
| `check_duplicates` | 30分ごと | 重複注文チェック | 検知時 Slack（上位5件＋一覧URL） |
| `check_credit_failures` | 1時間ごと | 与信落ち件数チェック | なし（`job_logs` に記録のみ） |

- 実行結果は `/batches/` 画面の「実行ログ（直近50件）」で確認できる。
- 間隔変更は `scheduler.py` の `add_job(..., "interval", ...)` を編集（`batches.html` の表示リストも手動で合わせる）。

## 運用手順

### 日次: 要対応受注のさばき
1. `/`（ダッシュボード）で 4カテゴリの件数を確認。
2. 件数のあるカテゴリのカードをクリックして一覧へ。
3. 各受注の内容を確認し、対応ボタンを実行（重複・テストは確認ダイアログあり）。
4. 対応後は自動で一覧に戻る。ECforce の問い合わせ履歴にも記録される。

### 日次/随時: 出荷CSV配布
1. `/batches/`（または `/` のクイックアクション）で「出荷CSV出力」を実行。
2. Drive にファイルが作成され、Chatwork にファイル名＋リンクが通知される。
3. `/batches/` の実行ログで `success` を確認。

## チェックリスト

### デプロイ前
- [ ] `ECFORCE_BASE_URL` / `ECFORCE_API_TOKEN` を Secrets に設定した
- [ ] 出荷CSVを使うなら `GOOGLE_CREDENTIALS_JSON` / `GOOGLE_DRIVE_FOLDER_ID` / `CHATWORK_*` を設定した
- [ ] 重複通知を使うなら `SLACK_BOT_TOKEN` / `SLACK_CHANNEL_ID` を設定した
- [ ] Drive フォルダをサービスアカウントに共有した
- [ ] 公開URLのアクセス範囲を限定した（認証は未実装）

### 破壊的操作の実行前（再与信・キャンセル・定期削除）
- [ ] 対象が正しい注文か（注文番号・顧客名・金額）を一覧で確認した
- [ ] テスト受注の「キャンセル・削除」は本番の定期購入を**削除**する点を理解している
- [ ] 「テスト受注を一括処理」（バッチ）は全テスト受注の決済を一括キャンセルする点を理解している

### 定期リリース確認
- [ ] `/batches/` 実行ログに `check_duplicates` / `check_credit_failures` の記録が出ている
- [ ] Slack に重複通知が届く（重複がある場合）

## トラブルシューティング

| 症状 | 想定原因 | 対処 |
|---|---|---|
| ダッシュボードに「ecforce API接続エラー」 | `ECFORCE_BASE_URL`/`ECFORCE_API_TOKEN` 未設定・誤り、ECforce 側障害 | 環境変数を確認。トークン形式は `Token token='...'` で送信される |
| 一覧が常に空 | `q[...]` の値がショップのステータス名と不一致 | `services/ecforce.py` のクエリ（例: `payment_status_eq=address_error`）を実データに合わせる |
| 各操作が 500 | ECforce のエンドポイント/権限不一致（`raise_for_status`） | 対象APIの有効化・トークン権限を確認 |
| Slack通知が来ない | `ok=false`（トークン/チャンネル/権限）、そもそも重複0件 | 例外メッセージ（`Slack error: ...`）を確認 |
| Chatwork通知が来ない | `CHATWORK_API_TOKEN`/`CHATWORK_ROOM_ID` 誤り | 実行ログの `error` メッセージを確認 |
| 出荷CSVバッチが error | Drive認証（`GOOGLE_CREDENTIALS_JSON` パース失敗）、フォルダ未共有 | JSON文字列の妥当性、フォルダ共有を確認 |
| 定期タスクが動かない | アプリが停止している（APScheduler はプロセス依存） | Replit の常駐/Run 状態を確認 |
| ログが消えた | `ec_manager.db` がコンテナ再生成で消失 | 重要ログは外部（Slack/Chatwork/ECforce履歴）で確認。永続化が必要なら外部DBへ移行 |

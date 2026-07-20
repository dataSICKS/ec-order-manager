# UI — ec-order-manager 画面設計

Jinja2 + Bootstrap 5.3（CDN）+ Bootstrap Icons 1.11。全画面が `base.html` を継承する2カラム（左サイドバー＋右メイン）レイアウト。独自 CSS は `base.html` 内 `<style>` のみ、`static/` は空（JS/CSSビルド不要）。

## デザイントークン

`base.html` の `<style>` で定義される最小限のトークン。

| トークン | 値 | 用途 |
|---|---|---|
| 背景 | `#f8f9fa`（body） | ページ全体 |
| サイドバー背景 | `#1a1a2e`（濃紺） | 左ナビ |
| ナビ文字（通常） | `#adb5bd` | `.sidebar .nav-link` |
| ナビ文字（hover/active） | `#fff` ＋ `rgba(255,255,255,0.1)` 背景、`border-radius: 6px` | 選択状態 |
| ブランド文字 | `#fff`, bold, `1.1rem` | `.sidebar .brand` |
| バッジ | `0.75rem` | `.badge-count` |

- 色のセマンティクスは Bootstrap のユーティリティに準拠: 住所不備=`text-danger`、与信落ち=`text-warning`、重複=`text-primary`、テスト受注=`text-secondary`。
- カードは `border-0 shadow-sm`（枠なし＋薄い影）で統一。

## レイアウト / ナビゲーション

- `base.html`: `container-fluid > row` の中で `col-md-2`（サイドバー）＋ `col-md-10`（メイン）。
- サイドバー項目（アイコンは Bootstrap Icons）。`active` 変数で現在地をハイライト。

| ナビ項目 | リンク | アイコン | `active` 値 |
|---|---|---|---|
| ダッシュボード | `/` | `bi-speedometer2` | `dashboard` |
| 住所不備 | `/orders/address-errors` | `bi-geo-alt` | `address_errors` |
| 与信落ち | `/orders/credit-failures` | `bi-credit-card` | `credit_failures` |
| 重複注文 | `/orders/duplicates` | `bi-files` | `duplicates` |
| テスト受注 | `/orders/test-orders` | `bi-bug` | `test_orders` |
| バッチ処理 | `/batches/` | `bi-gear` | `batches` |

- ブランド表示: `bi-box-seam` ＋「EC Manager」。

## 画面一覧（画面 × 役割 × UI）

| 画面 | テンプレート | 役割 | 主なUI |
|---|---|---|---|
| ダッシュボード | `index.html` | 4カテゴリ件数の俯瞰＋クイックアクション | 統計カード×4（クリックで各一覧へ）、クイックアクション2ボタン、ECforceエラー時は `alert-warning` |
| 住所不備 | `address_errors.html` | 住所の修正入力＋再与信 | 注文カード＋インラインの住所入力フォーム（姓/名/郵便/都道府県/市区町村/番地/建物） |
| 与信落ち | `credit_failures.html` | 再オーソリ実行 | テーブル（注文番号/顧客名/メール/金額/注文日）＋「再オーソリ」ボタン |
| 重複注文 | `duplicates.html` | 重複の決済キャンセル | テーブル（＋商品列）、行は `table-warning` 強調、キャンセルは `confirm` ダイアログ |
| テスト受注 | `test_orders.html` | 決済キャンセル＋定期削除 | テーブル、行は `table-secondary`、`subscription_id` を hidden 送信、`confirm` ダイアログ |
| バッチ処理 | `batches.html` | 手動バッチ実行＋ログ閲覧 | 手動実行カード、自動スケジュール表示カード、実行ログテーブル（直近50件、結果はバッジ色分け） |

## コンポーネント

- **統計カード**（ダッシュボード）: `card > card-body text-center`。`fs-1 fw-bold` の件数＋アイコン付きラベル。カード全体が該当一覧への `<a>`。
- **要対応テーブル**: `table table-hover bg-white shadow-sm rounded`、ヘッダ `table-light`。空時は `alert-success`（「〜はありません。」）。
- **住所修正フォーム**（カード内インライン）: `form-control-sm` を `row g-2` で配置。`required` 付き（建物名 `address2` のみ任意）。
- **操作ボタン**: 意味に応じて色分け（`btn-danger`=住所修正/重複キャンセル、`btn-warning`=再オーソリ、`btn-secondary`=テスト後始末、`btn-primary`=出荷CSV）。破壊的な重複/テストは `onsubmit="return confirm(...)"`。
- **実行結果バッジ**: `success`→`bg-success`（成功）、`error`→`bg-danger`（エラー）、それ以外→`bg-secondary`（実行中）。

## UX 方針

- **PRG（Post/Redirect/Get）**: すべての操作 POST は 303 で対応する一覧へ戻し、二重送信を防止。
- **破壊的操作の確認**: 決済キャンセル・テスト後始末は JS `confirm` を挟む（住所修正・再オーソリは即時実行）。
- **件数の見える化**: 見出しに `（{{ orders|length }}件）` を常時表示。空リストは緑のポジティブ表現で「対応不要」を明示。
- **フェイルソフト**: ECforce 接続エラーでもダッシュボードは開き、警告バナーで状況提示（画面全体を落とさない）。
- **色で状態を伝える**: 重複行は黄、テスト行はグレーで一覧上でも直感的に区別。

## レスポンシブ

- Bootstrap グリッド依存。サイドバー `col-md-2` / メイン `col-md-10`、統計カード `col-md-3`、バッチ画面カード `col-md-6`、住所フォーム入力は `col-md-3`/`col-md-4`。
- `md` ブレークポイント未満（スマホ）ではカラムが縦積みになる。テーブルは `table-responsive` で横スクロール対応。
- ハンバーガー等のモバイル専用ナビ最適化は未実装（サイドバーはそのまま縦積み表示）。

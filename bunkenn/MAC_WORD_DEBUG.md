# Mac Word Add-in Debug

## 目的

Mac の Word Desktop で、manifest 認識後の失敗点を次の 3 層に切り分ける。

1. manifest が task pane を開けるか
2. `taskpane.html` と `taskpane.js` が Word の WebView で正常初期化できるか
3. `VersionOverrides` と ribbon command を戻したときに壊れるか

## 追加した確認用ファイル

- `manifest.minimal.xml`
  - `VersionOverrides` なし
  - `SourceLocation` は `taskpane.minimal.html`
  - まずは task pane が開くかだけを見る
- `manifest.full.xml`
  - ribbon command と `VersionOverrides` あり
  - 現行の `taskpane.html` / `commands.html` を使う
- `manifest.production.xml`
  - `manifest.full.xml` と同じ内容
  - 既存フロー互換のために残す

## 先に確認しておくこと

- sideload 先:
  - `~/Library/Containers/com.microsoft.Word/Data/Documents/wef/manifest.xml`
- WebView キャッシュ:
  - `~/Library/Containers/com.Microsoft.OsfWebHost/Data/`
- 公開 URL:
  - `https://jolly-smoke-0e8ae9a10.7.azurestaticapps.net`

## 推奨の切り分け順

1. Word を終了する
2. `com.Microsoft.OsfWebHost` 配下のキャッシュを退避または削除する
3. `manifest.minimal.xml` を sideload 先に配置する
4. Word を起動し、アドインを開く
5. `taskpane.minimal.html` で `Ready` と `Host=Word` が見えるか確認する
6. これが成功したら `manifest.full.xml` に差し替える
7. ribbon button から task pane が開くか確認する

## 現時点で確認できた配信上の問題

### 1. 現行 `taskpane.html` は Office 初期化後に API に依存する

`taskpane.js` は `Office.onReady(...)` の後でセッション確認 API を呼ぶ。
そのため、Word 内で真っ白でなくても「開いたが進まない」に見えることがある。

初期ロード時に使う API:

- `POST /api/addin/auth/session`
- 認証後に `GET /api/addin/papers`

### 2. 配信 API は現時点でエラー応答を返している

確認時点では次の応答だった。

- `POST /api/addin/auth/session` -> `401`
- `GET /api/addin/papers?q=test` -> `500`
- どちらも本文に `bad_jwt` / `signature is invalid` が含まれる

この状態だと task pane 自体は開いても、認証カードや検索が正常に動かない可能性が高い。

### 3. icon URL が未配信

manifest が参照する `assets/icon-16.png` / `32` / `80` は現状 `404`。
さらに Static Web Apps の 404 rewrite により、存在しない icon URL へ HTML が返る。

これは ribbon command を戻したときの不具合要因になりうるので、デプロイ前に `static/assets/` 配下へ実ファイルを置くこと。

## `taskpane.html` 側の確認ポイント

### CSP

現状の Static Web Apps 応答ヘッダーには明示的な `Content-Security-Policy` が無い。
そのため CSP で `office.js` や相対パス JS が遮断されている形跡は今のところ薄い。

### 依存 JS パス

- `taskpane.html` -> `./taskpane.js?v=auth1`
- `commands.html` -> `./commands.js`

いずれも配信先で `200` を返している。

### WebView 内エラー

最初に確認すべきポイント:

- `taskpane.minimal.html` が見えるか
- `taskpane.html` で `Loading` のまま止まるか
- ステータス欄に API エラー文字列が出るか
- button を押したときだけ失敗するか

## 白画面・無反応・エラー時の調査順

1. `manifest.minimal.xml` で再現するか
2. しないなら `VersionOverrides` または command 側が原因
3. `manifest.full.xml` でのみ壊れるなら icon / command / ribbon を疑う
4. `taskpane.html` は開くが操作できないなら API 応答を見る
5. API が失敗しているなら WebView より先にバックエンド認証を直す

## 補足

- `commands.js` は `Office.actions.associate("noop", ...)` のみで、command 側ロジックは最小限
- したがって full manifest で壊れる場合は、command 実装より icon URL や `VersionOverrides` 定義を優先して疑う
- manifest を差し替えたのに挙動が変わらない場合は、Word 本体より `OsfWebHost` キャッシュ残りを疑う

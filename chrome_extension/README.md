# bunken Web Importer

Chrome / Brave から現在開いている論文ページを bunken に登録するための Manifest V3 拡張機能です。

## できること

- 論文ページからタイトル、著者、雑誌名、年、DOI、URL、abstract を取得
- `citation_pdf_url`、PDFリンク、ACS の DOI ページから PDF 候補を検出
- DOI がある場合は Crossref 側のメタデータで補完
- DOI またはタイトル・年で重複を確認
- 取得できるPDFは Supabase Storage の `paper-pdfs` に保存
- ACS などサーバー側取得がブロックされるPDFは、候補URLをブラウザで開いて手動アップロード
- Supabase refresh token を保存し、毎回パスワードを入力せずに利用

## インストール

1. bunken アプリのサイドバーから「Chrome拡張機能」をダウンロードします。
2. ZIPを展開します。
3. Chrome なら `chrome://extensions`、Brave なら `brave://extensions` を開きます。
4. デベロッパーモードをオンにします。
5. 「パッケージ化されていない拡張機能を読み込む」から展開したフォルダを選びます。
6. 拡張機能のポップアップを開き、bunken と同じメール・パスワードでログインします。

## アップデート

今の配布方式では、Chrome Web Store のような完全自動アップデートはできません。
拡張機能は起動時に最新版を確認し、新しい版がある場合は「最新版があります。bunkenアプリから再ダウンロードしてください。」と表示します。

表示された場合は、次の手順で更新してください。

1. bunken アプリを開きます。
2. サイドバーの「Chrome拡張機能」から最新版ZIPをダウンロードします。
3. ZIPを展開します。
4. Chrome なら `chrome://extensions`、Brave なら `brave://extensions` を開きます。
5. 既存の `bunken Web Importer` を削除します。
6. 「パッケージ化されていない拡張機能を読み込む」から、新しく展開したフォルダを選びます。
7. 必要に応じてもう一度ログインします。

## 使い方

1. 論文のランディングページを開きます。
2. 拡張機能を開き、「ページ情報を更新」で取得内容を確認します。
3. 「bunken に保存」を押します。
4. PDF候補が表示された場合は、「PDF候補を開く」からPDFを開き、必要なら bunken の文献詳細で手動アップロードします。

## 注意

- ACS など一部出版社は Cloudflare や機関認証により、Vercel API からPDFを直接取得できないことがあります。
- パスワードは保存しません。ログイン後は refresh token でセッションを更新します。
- 共有PCで使う場合は、ポップアップの「ログアウト」を押してください。

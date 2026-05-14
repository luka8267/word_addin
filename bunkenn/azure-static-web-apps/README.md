# Azure Static Web Apps

`bunken Word` を無料寄りでクラウド公開するための雛形です。

構成:
- `static/`
  - Word Add-in の静的ファイル
- `api/`
  - Azure Functions (Python)

公開後の想定URL:
- `https://<your-app>.azurestaticapps.net/taskpane.html`
- `https://<your-app>.azurestaticapps.net/api/addin/papers?q=...`

## フォルダ

```text
azure-static-web-apps/
  README.md
  static/
    taskpane.html
    taskpane.js
    commands.html
    commands.js
    assets/
  api/
    host.json
    requirements.txt
    shared/
      bunken_service.py
      bunken_models.py
      data_access.py
    addin_auth_session/
      function.json
      __init__.py
    addin_papers/
      function.json
      __init__.py
    addin_citations_format/
      function.json
      __init__.py
    addin_bibliography_format/
      function.json
      __init__.py
    addin_documents_citations/
      function.json
      __init__.py
    addin_documents_sync/
      function.json
      __init__.py
```

## 方針

- Add-in の静的UIとAPIを同じオリジンに置く
- Azure Static Web Apps の Free プランを想定
- API は Azure Functions の HTTP Trigger を使う
- MVP では `DEFAULT_USER_ID` の固定を残し、後で認証へ置き換える

## 次の作業

1. Azure Static Web Apps に新規アプリを作る
2. `static/` を静的配信
3. `api/` を Functions として配信
4. 公開URLで `generate_manifest.py` を実行

## GitHub Actions

Azure 側で GitHub リポジトリ連携を使う場合は、雛形として
`github-actions-azure-static-web-apps.yml` を使える。

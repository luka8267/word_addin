# Word Add-in Integration

## 現在の状態

このリポジトリには、Word Add-in から叩くローカル API として
`addin_local_api.py` を追加しています。

対応エンドポイント:
- `POST /api/addin/auth/session`
- `GET /api/addin/papers?q=...`
- `POST /api/addin/citations/format`
- `POST /api/addin/bibliography/format`

## 起動

```powershell
$env:BUNKEN_ADDIN_TLS_CERT="C:\temp\bunkencert\cert.pem"
$env:BUNKEN_ADDIN_TLS_KEY="C:\temp\bunkencert\key.pem"
python .\addin_local_api.py
```

既定:
- Host: `127.0.0.1`
- Port: `8765`
- User ID: `1`

環境変数で変更可能:

```powershell
$env:BUNKEN_ADDIN_PORT="8765"
$env:BUNKEN_DEFAULT_USER_ID="1"
python .\addin_local_api.py
```

## 前提

- `papers.db` の `users.id = 1` の文献を返す
- 現時点ではローカル単一ユーザー向けの試作
- Word Add-in 側ではこの API ベース URL に接続する

## 次の接続先

Add-in 側の `API_BASE_URL` は、将来的にはこのローカル API か
同等の本番 API に合わせて設定する。

例:
- `https://localhost:8765`

## サンプル文献投入

`papers.db` が空のときは、次で試験用の1件を追加できる。

```powershell
python .\seed_sample_paper.py
```

## 制約

- 現時点では簡易認証
- DOI は `papers.db` スキーマに列が無いため未返却
- 文中引用は簡易整形

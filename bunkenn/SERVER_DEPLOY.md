# Server Deploy

`bunken Word` を他の PC でも使えるようにするには、`localhost` をやめて 1 つの公開 HTTPS URL にまとめる。

## 目標構成

- 例: `https://bunken.example.com`
- 同じオリジンで次を返す
  - `/taskpane.html`
  - `/taskpane.js`
  - `/commands.html`
  - `/commands.js`
  - `/assets/*`
  - `/api/addin/*`

この形にすると、Word Web から見てもクロスオリジンにならず扱いやすい。

## 今のコードで使うもの

- API と静的配信
  - [addin_local_api.py](C:/Users/run_r/OneDrive/ドキュメント/bunkenn/addin_local_api.py)
- 本番 manifest 生成
  - [generate_manifest.py](C:/Users/run_r/OneDrive/ドキュメント/bunkenn/generate_manifest.py)
- manifest テンプレート
  - [manifest.production.xml.template](C:/Users/run_r/AppData/Local/Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState/games/com.mojang/development_behavior_packs/bunken-word-addin/manifest/manifest.production.xml.template)

## 最短の公開方法

1. 公開できる Windows PC か VPS を 1 台用意する
2. そのマシンで `bunkenn` と `bunken-word-addin` を配置する
3. `addin_local_api.py` を `0.0.0.0` で待ち受ける
4. リバースプロキシで公開 HTTPS を付ける
5. その公開 URL で manifest を生成する

## 必要な環境変数

```powershell
$env:BUNKEN_ADDIN_HOST="0.0.0.0"
$env:BUNKEN_ADDIN_PORT="443"
$env:BUNKEN_ADDIN_TLS_CERT="C:\path\to\fullchain.pem"
$env:BUNKEN_ADDIN_TLS_KEY="C:\path\to\privkey.pem"
python .\addin_local_api.py
```

実運用では、Python が直接 443 を持つよりも Nginx や Caddy を前段に置く方が安全。

## manifest 生成

```powershell
$env:BUNKEN_PUBLIC_BASE_URL="https://bunken.example.com"
python .\generate_manifest.py
```

生成先:
- [manifest.production.xml](C:/Users/run_r/OneDrive/ドキュメント/bunkenn/manifest.production.xml)

これを Word Web の `Upload My Add-in` に使う。

## 本番化で直すべき点

- SQLite の `papers.db` を共有 DB に置き換える
- `DEFAULT_USER_ID=1` の固定をやめる
- ログイン済みユーザー判定を実装する
- 参考文献スタイルと複数文献引用を強化する

## おすすめの次段階

1. まずは自宅内や同一 LAN で 1 台を公開役にして動かす
2. その後にドメインと HTTPS を付ける
3. 最後に共有 DB とログインを入れる

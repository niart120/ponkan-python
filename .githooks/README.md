# Git Hooks

このディレクトリは Git hooks の正本です。

clone 後に一度だけ次のいずれかを実行してください。

```console
scripts/install-git-hooks.ps1
```

```console
sh scripts/install-git-hooks.sh
```

設定される値:

```console
git config core.hooksPath .githooks
```

Git は tracked hooks を clone 時に自動有効化しません。これは、リポジトリ内の任意コードが clone だけで実行可能になることを避けるための安全設計です。

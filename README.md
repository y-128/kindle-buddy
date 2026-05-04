# claude-buddy (Kindle e-ink port)

[m5-paper-buddy](https://github.com/op7418/m5-paper-buddy) をKindleのe-inkディスプレイで動かすポートプロジェクト。  
Claude Codeのセッション状態・承認リクエスト・ログをKindle画面に表示し、タッチで承認/拒否できる。

## 機能

- **ダッシュボード表示** — モデル名・フェーズ・現在のタスク・ログをリアルタイム表示
- **承認カード** — bash実行・ファイル編集・書き込みの許可/拒否をタッチで操作。右上に残り秒数表示
- **マルチセッション** — 複数のClaude Codeウィンドウを一覧表示・タップで切り替え。他セッションの承認リクエストは自動切り替え
- **コンテキスト使用量** — プログレスバーとパーセント表示でトークン消費を可視化
- **DND モード** — 承認リクエストを自動許可
- **KUAL 拡張** — Kindle のランチャーから起動・停止・ログ確認

---

## 対象デバイス

| モデル | Serial | Jailbreak方法 | 状態 |
|---|---|---|---|
| Kindle 8th gen (2016) | sy69jl | WinterBreak | ✅ 対応 |

---

## セットアップ手順

### 0. Jailbreak

**sy69jl (K8) — WinterBreak**
- firmware 5.16.4 – 5.18.0.2 が条件
- 接続前に必ず**機内モードをON**（OTA更新防止）

### 1. ホットフィックス + KUAL + MRPI

1. `Update_hotfix_universal.bin` をKindleルートにコピー → Settings → Update Your Kindle
2. `mrpackages/` フォルダ + `KUAL-KDK-2.0.azw2` (documents/) をコピー
3. 検索バーに `;log mrpi` と入力 → Enter

### 2. MRPI でパッケージインストール

以下の `.bin` ファイルを `mrpackages/` に置いてKUAL → MRPIから実行:

- `Update_python3_0.15.N_install_pw2_and_up.bin` — Python 3.9.8
- `Update_usbnet_0.22.N_install_pw2_and_up.bin` — USBNet + SSH

パッケージは [NiLuJe's snapshots (MobileRead)](https://www.mobileread.com/forums/showthread.php?t=225030) からダウンロード。

> py-fbink / Pillow / libevdev は Python スナップショットに同梱済み。

### 3. SSH接続確認

WiFi経由で接続する。Kindle側で KUAL → USBNetwork → Allow SSH over WiFi → Toggle USBNetwork ON。

```sh
ssh root@<KindleのWiFi IP>
```

初回のパスワードプロンプトは空Enter。

KindleのWiFi IPはMacから:
```sh
arp -a | grep <KindleのMACアドレス>
```

SSHが起動しているか確認:
```sh
nc -vz <KindleのWiFi IP> 22
```

`Connection refused` の場合、IPは合っているがKindle側のSSHサーバが起動していない。
KindleをUSBストレージとしてFinderで開いている場合は安全に取り出し、KUAL → USBNetwork →
Toggle USBNetwork OFF → ON でSSHを再起動する。

### 3.1. パスワードなしログイン → 鍵ログイン方式

USBNetwork の Kindle 側 `authorized_keys` は、通常の `~/.ssh/authorized_keys` ではなく
`/mnt/us/usbnet/etc/authorized_keys` に置く。

Mac側でKindle用の鍵を作成:
```sh
ssh-keygen -t rsa -b 4096 -f ~/.ssh/kindle_buddy -C "kindle-buddy"
```

> 古い Kindle / Dropbear では `ed25519` が通らない場合があるため、まずは `rsa` を使う。

公開鍵をKindleへコピー:
```sh
scp ~/.ssh/kindle_buddy.pub root@<KINDLE_IP>:/mnt/us/usbnet/etc/authorized_keys
```

Finderでコピーする場合:
1. KindleをUSBでMacに接続し、FinderでKindleのUSBストレージを開く。
2. `usbnet/etc/` フォルダを開く。Kindle上ではここが `/mnt/us/usbnet/etc/` に対応する。
3. Finderで `Cmd-Shift-G` → `~/.ssh` を開き、`kindle_buddy.pub` を探す。
4. `kindle_buddy.pub` を `usbnet/etc/` にコピーし、コピー先のファイル名を `authorized_keys` に変更する。
5. Kindleを安全に取り出し、KUAL → USBNetwork → Toggle USBNetwork OFF → ON でSSHを再起動する。

既に `authorized_keys` がある場合は上書きせず、Kindle側で追記:
```sh
ssh root@<KINDLE_IP>
cat >> /mnt/us/usbnet/etc/authorized_keys
# Mac側の ~/.ssh/kindle_buddy.pub の1行を貼り付け → Ctrl-D
```

鍵ログインを確認:
```sh
ssh -i ~/.ssh/kindle_buddy -o PasswordAuthentication=no root@<KINDLE_IP>
```

成功したら、Mac側の `~/.ssh/config` に登録:
```sh
mkdir -p ~/.ssh
touch ~/.ssh/config
chmod 700 ~/.ssh
chmod 600 ~/.ssh/config
chmod 600 ~/.ssh/kindle_buddy
```

> 上の `chmod` はMac側で実行する。`[root@kindle root]#` のSSHセッション内では実行しない。

```sshconfig
Host kindle-buddy
  HostName <KINDLE_IP>
  User root
  IdentityFile ~/.ssh/kindle_buddy
  IdentitiesOnly yes
```

以後は:
```sh
ssh kindle-buddy
cd ~/claude-buddy
scp -r kindle kindle-buddy:/mnt/us/buddy
```

パスワード認証を無効化する場合は、**必ず鍵ログイン成功後**に Kindle 側の
`/mnt/us/usbnet/etc/config` を編集し、パスワードログインを許可する項目を無効にする。
これはKindle側の既存ファイルで、Mac側の `~/.ssh/config` とは別。
USBNetwork / Dropbear の版によって項目名が違うため、まず該当行を確認:
```sh
grep -nE 'PASS|PASSWORD|DROPBEAR|SSHD|AUTH' /mnt/us/usbnet/etc/config
```

`ALLOW_PASSWORD_LOGIN="true"` のような項目があれば `false` にする。Dropbear の起動オプションを
直接指定する形式なら、`-s`（password login disabled）を追加する。
反映後は KUAL → USBNetwork → Toggle USBNetwork OFF → ON で SSH を再起動し、別ターミナルで:
```sh
ssh -i ~/.ssh/kindle_buddy -o PasswordAuthentication=no root@<KINDLE_IP>
```

で再確認する。失敗した場合に戻せるよう、確認が終わるまで既存のSSHセッションは閉じない。

### 4. アプリのデプロイ

以下はMac側のターミナルで実行する。`[root@kindle root]#` のSSHセッション内では実行しない。

```sh
cd ~/claude-buddy
bash kindle/install/deploy.sh
```

このスクリプトは以下を両方コピーする:
- アプリ本体: `/mnt/us/buddy/app`
- KUAL拡張: `/mnt/us/extensions/ClaudeBuddy`

KUALに `Claude Buddy` が出ない場合は、Kindle側で配置を確認:
```sh
ls -la /mnt/us/extensions/ClaudeBuddy
```

`config.xml` / `menu.json` / `start.sh` が見えれば配置済み。KUALを開き直すか、
Kindleを再起動してから再確認する。

---

## アプリの起動

### 手動起動（テスト用）

Mac側から直接起動:
```sh
ssh kindle-buddy 'cd /mnt/us/buddy/app && python3 buddy.py --transport wifi --tcp-port 9877 --log-level DEBUG'
```

SSHでKindleに入ってから起動する場合:
```sh
ssh kindle-buddy
cd /mnt/us/buddy/app
python3 buddy.py --transport wifi --tcp-port 9877 --log-level DEBUG
```

`[root@kindle root]#` が表示されているだけなら、まだアプリは起動していない。
そのプロンプトで `cd /mnt/us/buddy/app` 以降を実行する。

起動できている場合は、Kindle側ログに以下が出る:
```text
[wifi] listening on 0.0.0.0:9877
buddy ready
```

Mac側 bridge がつながると:
```text
[wifi] connected from ...
[rx] {"total":...
[render] dashboard ...
```

が出る。`[wifi] connected from ...` はあるのに `[rx]` や `[render]` が出ない場合は、
Mac側 bridge が状態JSONを送れていない。

`[render]` が出ているのに画面が変わらない場合は、Kindle側でFBInkの表示テスト:
```sh
fbink -q -pmh "Claude Buddy FBInk test"
```

これも表示されない場合、アプリではなくKindle側の表示更新/FBInk環境の問題。

### KUAL経由（常用）

`kindle/install/deploy.sh` 実行で `kual-extension/` は自動で `extensions/ClaudeBuddy` に配置される。  
Kindle側で KUAL → Claude Buddy → Start Buddy。
起動失敗時は KUAL → Claude Buddy → Status で状態確認。

Buddy起動中は `/dev/input/event0` をgrabし、タッチが背面のKindle UIへ貫通しないようにする。
`View Log` で `[touch] grabbed /dev/input/event0` が出ていれば有効。
Stop Buddy はプロセス停止のみ行い、Kindle画面の強制クリアはしない。

画面上部のKindle時計/status領域はセーフゾーンとしてBuddy側では描画しない。
Buddy画面内にはバッテリー残量を表示しない。

メイン画面:
- `SETTINGS`: 設定画面を開く
- `EXIT`: Buddyプロセスを終了
- 右下DNDゾーン: DND切り替え

設定画面:
- `BACK`: メイン画面へ戻る
- `EXIT`: Buddyプロセスを終了
- `DND`: DND切り替え
- `Full refresh`: Buddy描画領域を黒→白で消してから再描画する全画面更新

ログ確認:
```sh
tail -f /mnt/us/buddy/buddy.log
```

---

## プロジェクト構造

```
kindle/
├── app/
│   ├── buddy.py        # メインループ（transport + touch + display統合）
│   ├── display.py      # PIL → FBInk レンダリング（600×800）
│   ├── state.py        # TamaState JSON解析・スレッドセーフな状態管理
│   ├── transport.py    # WiFi TCP (port 9877) + USB Serial
│   ├── touch.py        # evdev タッチ入力 (/dev/input/event0)
│   ├── frames.py       # バディAAアート（IDLE/BUSY/ATTENTION等）
│   ├── layout.py       # 座標・フォントサイズ定数
│   └── fonts/          # 日本語対応フォント (NotoSansCJKjp-Regular.otf など)
├── kual-extension/     # KUAL start/stop スクリプト
└── install/
    └── deploy.sh       # rsync デプロイスクリプト
```

---

## 技術メモ

### FBInk (Python CFFI)

インストール済みモジュールは `_fbink`（`pyfbink` ではない）。  
CFFI形式で初期化:

```python
import _fbink
lib, ffi = _fbink.lib, _fbink.ffi
cfg = ffi.new("FBInkConfig *")
lib.fbink_init(lib.FBFD_AUTO, cfg)
```

### 画面への書き込み

`fbink_print_raw_data` は rotation=3 による余計な座標変換をかけるため使用不可。  
PIL画像を **直接 `/dev/fb0` に書き込み**、FBInkはリフレッシュトリガーにだけ使う:

```python
raw = image.tobytes()  # 600×800, 8bpp, no rotation needed
LINE = 608  # physical line_length (600px + 8 padding)

with open("/dev/fb0", "r+b") as fb:
    for row in range(800):
        fb.seek(row * LINE)
        fb.write(raw[row * 600: row * 600 + 600])

cfg = ffi.new("FBInkConfig *")
cfg.wfm_mode = lib.WFM_GC16  # full refresh
lib.fbink_refresh(lib.FBFD_AUTO, 0, 0, 0, 0, cfg)
```

座標系: `fb(col, row)` → `display(col, row)` 直接マッピング（変換不要）。

### タッチデバイス

`/dev/input/event0` (zforce2)。座標は正常 (X: 0–599, Y: 0–799)、キャリブレーション不要。

### WiFi SSH

- SSHはWiFi経由で接続する。
- KindleのWiFi IPは固定値としてREADMEには書かず、`arp -a` などで確認する。
- 鍵ログイン確認後は `ssh kindle-buddy` を使う。

---

## 実装状況

| フェーズ | 内容 | 状態 |
|---|---|---|
| 0 | Jailbreak + Python + USBNet + SSH | ✅ 完了 |
| 1 | FBInk画面描画確認 | ✅ 完了 |
| 2 | タッチ入力確認 | ✅ 完了 |
| 3 | state.py + frames.py | ✅ 完了 |
| 4 | display.py 実機描画確認 | ✅ 完了 |
| 5 | buddy.py 統合起動 | ✅ 完了 |
| 6 | transport.py WiFi接続テスト | ✅ 完了 |
| 7 | claude_code_bridge.py TCP対応 (`--transport tcp --kindle-ip`) | ✅ 完了 |
| 8 | KUAL拡張セットアップ（deploy時に `extensions/ClaudeBuddy` へ自動配置） | ✅ 完了 |
| 9 | 承認カード右上にカウントダウン表示（30s→0s、残り10s以下で強調） | ✅ 完了 |
| 10 | マルチセッション表示・タップ切り替え・他セッション承認時の自動切り替え | ✅ 完了 |
| 11 | コンテキスト使用量プログレスバー + パーセント表示 | ✅ 完了 |

---

## Mac側セットアップ

`tools/claude_code_bridge.py` は TCP をサポート済み:

```sh
python3 tools/claude_code_bridge.py --transport tcp --kindle-ip KINDLE_WIFI_IP
```

`KINDLE_WIFI_IP` は実際のIPに置き換える。`<KindleのWiFi IP>` のように `<...>` を
そのままzshに貼るとリダイレクト扱いになり、parse error になる。

`OSError: [Errno 48] Address already in use` が出た場合は、Mac側のHTTP待受ポート
`127.0.0.1:9876` が既に使用中。別ポートで起動する:

```sh
python3 tools/claude_code_bridge.py --transport tcp --kindle-ip KINDLE_WIFI_IP --http-port 9878
```

Claude Code plugin利用時は:

```sh
BUDDY_TRANSPORT=tcp KINDLE_IP=KINDLE_WIFI_IP BUDDY_HTTP_PORT=9878 bash plugin/scripts/start.sh
```

Claude Codeのterminal sessionで実イベントを表示するには、hooksをClaude Code設定へ入れる必要がある:

```sh
cd ~/claude-buddy
tools/install_claude_hooks.py
```

このスクリプトは `~/.claude/settings.json` をバックアップしてから、
`plugin/settings/hooks.json` の `hooks` をマージする。反映にはClaude Codeセッションの再起動が必要。

`daemon already running` が出た場合は、既存のbridgeデーモンが残っている。
状態確認:
```sh
bash plugin/scripts/status.sh
```

止めてから起動し直す:
```sh
bash plugin/scripts/stop.sh
BUDDY_TRANSPORT=tcp KINDLE_IP=KINDLE_WIFI_IP BUDDY_HTTP_PORT=9878 bash plugin/scripts/start.sh
```

ログ確認:
```sh
tail -f ~/.claude-buddy/daemon.log
```

### bridge自動起動（Mac）

Macログイン時にbridgeを自動起動する場合は LaunchAgent を使う。
Claude Code hooks のデフォルトは `127.0.0.1:9876` なので、通常はHTTPポート `9876` にする。

```sh
cd ~/claude-buddy
tools/install_bridge_launch_agent.sh KINDLE_WIFI_IP 9876
```

例:
```sh
tools/install_bridge_launch_agent.sh 192.168.x.x 9876
```

状態確認:
```sh
launchctl print gui/$(id -u)/com.kindle-buddy.bridge
tail -f ~/.claude-buddy/launchd.err.log
```

解除:
```sh
tools/uninstall_bridge_launch_agent.sh
```

`9878` など別ポートで自動起動する場合は、Claude Code hooks 側のPOST先も同じポートに合わせる。

### bridge動作テスト

実際のClaude Codeセッションを待たずに、疑似hookを送ってKindle表示を確認できる。
bridgeが `--http-port 9878` または `BUDDY_HTTP_PORT=9878` で起動している状態で:

```sh
cd ~/claude-buddy
bash tools/test_buddy_hooks.sh dashboard
```

承認カードのテスト:
```sh
bash tools/test_buddy_hooks.sh approval
```

質問カードのテスト:
```sh
bash tools/test_buddy_hooks.sh question
```

`approval` / `question` はKindle側でタップするか、30秒待つと終了する。

### モデル名表示

bridgeはClaude Codeのhook payloadまたはtranscriptから使用モデルを読み取り、
Kindleの `MODEL` 欄に短縮表示する。

例:
- `claude-sonnet-4-5-...` → `Sonnet 4.5`
- `claude-opus-4.1` → `Opus 4.1`
- `claude-3-5-haiku-...` → `Haiku 3.5`

モデル名はassistantメッセージがtranscriptへ書かれた後に反映されることがある。

---

## License

GPL-3.0 — see [LICENSE](LICENSE)

This project is a Kindle e-ink port inspired by
[m5-paper-buddy](https://github.com/op7418/m5-paper-buddy) by op7418,
which is also licensed under GPL-3.0.

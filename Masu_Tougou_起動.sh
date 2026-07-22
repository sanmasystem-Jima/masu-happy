#!/usr/bin/env bash
# 桝Happy 集水桝 一括生成ツール ランチャー (Lubuntu / Linux用)

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"
VENV_PY="$VENV_DIR/bin/python3"

echo "============================================"
echo "  集水桝 一括生成ツール 起動"
echo "============================================"
echo

pause_and_exit() {
    echo
    read -rp "Enterキーを押すと終了します..." _
    exit "${1:-1}"
}

# --- Python本体の検出 ---
PYTHON_BIN=""
for cand in python3 python; do
    if command -v "$cand" >/dev/null 2>&1; then
        PYTHON_BIN="$cand"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "[エラー] Python3 が見つかりません。"
    echo "以下でインストールしてください:"
    echo "  sudo apt install python3 python3-venv python3-pip"
    pause_and_exit 1
fi

# --- 仮想環境(.venv)の確認・（壊れていれば）再作成 ---
if [ ! -x "$VENV_PY" ] || ! "$VENV_PY" --version >/dev/null 2>&1; then
    if [ -d "$VENV_DIR" ]; then
        echo "既存の仮想環境が壊れているため、作り直します..."
        rm -rf "$VENV_DIR"
    else
        echo "初回セットアップ: 仮想環境を作成しています..."
    fi
    # NTFS等のドライブではシンボリックリンクが壊れることがあるため --copies を使用
    if ! "$PYTHON_BIN" -m venv --copies "$VENV_DIR"; then
        echo "[エラー] 仮想環境の作成に失敗しました。"
        echo "  sudo apt install python3-venv  を実行してから再度お試しください。"
        pause_and_exit 1
    fi
    echo "仮想環境を作成しました。"
    echo
fi

# --- 依存パッケージの確認・インストール ---
if ! "$VENV_PY" -c "import ezdxf" >/dev/null 2>&1; then
    echo "必要なパッケージをインストールしています...（初回のみ）"
    "$VENV_PY" -m pip install --upgrade pip >/dev/null 2>&1
    if ! "$VENV_PY" -m pip install -r "$SCRIPT_DIR/requirements.txt"; then
        echo "[エラー] パッケージのインストールに失敗しました。"
        echo "インターネット接続を確認してから、もう一度実行してください。"
        pause_and_exit 1
    fi
    echo "インストールが完了しました。"
    echo
fi

# --- 本体を起動 ---
"$VENV_PY" "$SCRIPT_DIR/00_Masu_Tougou.py"
STATUS=$?

if [ "$STATUS" -ne 0 ]; then
    echo
    echo "[エラー] 処理中にエラーが発生しました。上のログを確認してください。"
fi

pause_and_exit "$STATUS"

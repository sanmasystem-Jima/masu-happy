@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "VENV_DIR=%~dp0.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "PY_LAUNCHER="

echo ============================================
echo   集水桝 一括生成ツール 起動
echo ============================================
echo.

rem --- Python本体の検出 ---
where py >nul 2>nul
if %errorlevel%==0 (
    set "PY_LAUNCHER=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PY_LAUNCHER=python"
    ) else (
        echo [エラー] Python が見つかりません。
        echo Python 3.10 以上をインストールしてから、もう一度実行してください。
        echo   https://www.python.org/downloads/
        goto :end
    )
)

rem --- 仮想環境(.venv)が無ければ作成 ---
if not exist "%VENV_PY%" (
    echo 初回セットアップ: 仮想環境を作成しています...
    %PY_LAUNCHER% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [エラー] 仮想環境の作成に失敗しました。
        echo Python 3.10 以上が正しくインストールされているか確認してください。
        goto :end
    )
    echo 仮想環境を作成しました。
    echo.
)

rem --- 依存パッケージの確認・インストール ---
"%VENV_PY%" -c "import ezdxf" >nul 2>nul
if errorlevel 1 (
    echo 必要なパッケージをインストールしています...（初回のみ・少し時間がかかります）
    "%VENV_PY%" -m pip install --upgrade pip >nul 2>nul
    "%VENV_PY%" -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo [エラー] パッケージのインストールに失敗しました。
        echo インターネット接続を確認してから、もう一度実行してください。
        goto :end
    )
    echo インストールが完了しました。
    echo.
)

rem --- 本体を起動 ---
"%VENV_PY%" "%~dp000_Masu_Tougou.py"
if errorlevel 1 (
    echo.
    echo [エラー] 処理中にエラーが発生しました。上のログを確認してください。
)

:end
echo.
pause

@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
echo.
echo ================================================
echo    TELEGRAM BOT - SOZLASH DASTURI
echo ================================================
echo.

REM Python bor-yo'qligini tekshirish
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python topilmadi!
    echo.
    echo Python yuklab olish uchun brauzer ochilmoqda...
    start https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    echo.
    echo Python o'rnatilgandan so'ng bu faylni qayta ishga tushiring.
    echo MUHIM: O'rnatishda "Add Python to PATH" ni belgilang!
    pause
    exit
)

echo [OK] Python topildi.
echo.

REM pip kutubxonalarini o'rnatish
echo [..] Kerakli kutubxonalar o'rnatilmoqda...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [!] Xato yuz berdi. Internet aloqasini tekshiring.
    pause
    exit
)
echo [OK] Kutubxonalar o'rnatildi.
echo.

REM .env fayli bor-yo'qligini tekshirish
if not exist ".env" (
    echo ================================================
    echo   SOZLASH - Bir marta bajariladi
    echo ================================================
    echo.
    set /p BOT_TOKEN="BotFather dan olgan TOKEN ni kiriting: "
    set /p ADMIN_ID="Sizning Telegram ID raqamingiz: "
    echo.
    
    (
        echo BOT_TOKEN=!BOT_TOKEN!
        echo ADMIN_ID=!ADMIN_ID!
        echo DB_PATH=bot_data.db
    ) > .env
    
    echo [OK] Sozlamalar saqlandi!
    echo.
)

echo ================================================
echo   BOT ISHGA TUSHMOQDA...
echo   Toxtatish uchun: Ctrl+C
echo ================================================
echo.
python bot.py
pause

@echo off
cd /d "%~dp0"
echo ===============================================
echo  GPT Image Studio
echo ===============================================
echo.

if not exist .env (
    echo [!] Brak pliku .env. Skopiuj .env.example -^> .env i wpisz swoje klucze.
    echo.
    pause
    exit /b 1
)

echo Uruchamiam Streamlit...
streamlit run app.py
pause

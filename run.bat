@echo off
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Initializing database...
python init_db.py

echo.
echo Starting Flask application...
python app.py

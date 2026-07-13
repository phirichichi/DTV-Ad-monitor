#backend/run_ingestion_worker.bat
@echo off
cd /d "%~dp0"

set DB_HOST=localhost
set REDIS_HOST=localhost
set KAFKA_BOOTSTRAP_SERVERS=localhost:19092
set PYTHONPATH=.

call ..\.venv\Scripts\activate

python -m app.workers.ingestion_worker

pause
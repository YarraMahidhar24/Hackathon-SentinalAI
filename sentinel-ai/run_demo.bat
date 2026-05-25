@echo off
echo 🛡️  SENTINEL-AI: Initializing...
python -m sentinel.storage.duckdb_store --init
python -m sentinel.storage.chroma_store --seed
echo 🚀 Starting dashboard...
streamlit run dashboard/app.py
pause


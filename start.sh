#!/bin/bash

# Python環境のセットアップ
python -m pip install --upgrade pip
pip install -r requirements.txt

# アプリケーションの実行
exec uvicorn main:app --host 0.0.0.0 --port $PORT

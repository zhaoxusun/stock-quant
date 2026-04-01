#!/bin/sh

SCRIPT_DIR=$(dirname "$0")
cd "$SCRIPT_DIR"
python3.13 -m venv venv13
source venv13/bin/activate
pip install -r requirements-13.txt
python frontend/frontend_app.py
#!/bin/bash
# Build script for Render deployment.
# Builds the frontend, then the Python backend serves it as static files.

set -e

echo "=== Building frontend ==="
cd web
npm install
npm run build
cd ..

echo "=== Installing Python dependencies ==="
pip install -r api/requirements.txt

echo "=== Build complete ==="

#!/usr/bin/env bash
# Install backend deps and build the vibe-coded front end (if present) into frontend/dist.
set -e
pip install -q -r requirements.txt
if [ -f frontend/package.json ]; then
  cd frontend
  npm ci --silent || npm install --silent
  npm run build
fi

#!/usr/bin/env bash
# Serve the API and the built front end from one origin.
exec uvicorn api:app --host 0.0.0.0 --port "${PORT:-8000}"

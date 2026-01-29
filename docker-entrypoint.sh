#!/bin/bash
set -e

echo "=== Baulkham Hills & Castle Hill Property Tracker ==="
echo "Database: ${BAULKANDCASTLE_DB_PATH}"
echo "API: http://0.0.0.0:${BAULKANDCASTLE_API_PORT}"

# Start cron in background (for scheduled scraping)
if [ "${ENABLE_CRON:-false}" = "true" ]; then
    echo "Starting cron scheduler..."
    cron
fi

# Run initial scrape if no DB exists and AUTO_SCRAPE is set
if [ "${AUTO_SCRAPE:-false}" = "true" ] && [ ! -f "${BAULKANDCASTLE_DB_PATH}" ]; then
    echo "No database found. Running initial scrape..."
    python baulkandcastle_scraper.py --daily || echo "Initial scrape failed (non-fatal)"
fi

# Start the proper Flask server (app factory with all routes + frontend)
echo "Starting API server..."
exec python -c "
from baulkandcastle.api.server import run_server
import os
run_server(
    host=os.environ.get('BAULKANDCASTLE_API_HOST', '0.0.0.0'),
    port=int(os.environ.get('BAULKANDCASTLE_API_PORT', '5000'))
)
"

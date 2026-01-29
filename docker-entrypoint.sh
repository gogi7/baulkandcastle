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

# Start the Flask API server (serves frontend + API)
echo "Starting API server..."
exec python api_server.py --host "${BAULKANDCASTLE_API_HOST}" --port "${BAULKANDCASTLE_API_PORT}"

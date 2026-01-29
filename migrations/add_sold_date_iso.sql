-- Migration: Add sold_date_iso column to listing_history
-- Purpose: Standardized ISO date format for ML model training
-- Run: sqlite3 baulkandcastle_properties.db < migrations/add_sold_date_iso.sql

-- Add the new column (will fail silently if already exists)
ALTER TABLE listing_history ADD COLUMN sold_date_iso TEXT;

-- Populate from existing sold_date values
-- Handle format "DD MMM YYYY" (e.g., "15 Jan 2024")
UPDATE listing_history
SET sold_date_iso =
    CASE
        -- Already in ISO format (YYYY-MM-DD)
        WHEN sold_date LIKE '____-__-__' THEN substr(sold_date, 1, 10)
        WHEN sold_date LIKE '____-__-__%' THEN substr(sold_date, 1, 10)
        -- DD MMM YYYY format - convert to ISO
        WHEN sold_date LIKE '__ Jan ____' THEN
            substr(sold_date, 8, 4) || '-01-' || substr(sold_date, 1, 2)
        WHEN sold_date LIKE '__ Feb ____' THEN
            substr(sold_date, 8, 4) || '-02-' || substr(sold_date, 1, 2)
        WHEN sold_date LIKE '__ Mar ____' THEN
            substr(sold_date, 8, 4) || '-03-' || substr(sold_date, 1, 2)
        WHEN sold_date LIKE '__ Apr ____' THEN
            substr(sold_date, 8, 4) || '-04-' || substr(sold_date, 1, 2)
        WHEN sold_date LIKE '__ May ____' THEN
            substr(sold_date, 8, 4) || '-05-' || substr(sold_date, 1, 2)
        WHEN sold_date LIKE '__ Jun ____' THEN
            substr(sold_date, 8, 4) || '-06-' || substr(sold_date, 1, 2)
        WHEN sold_date LIKE '__ Jul ____' THEN
            substr(sold_date, 8, 4) || '-07-' || substr(sold_date, 1, 2)
        WHEN sold_date LIKE '__ Aug ____' THEN
            substr(sold_date, 8, 4) || '-08-' || substr(sold_date, 1, 2)
        WHEN sold_date LIKE '__ Sep ____' THEN
            substr(sold_date, 8, 4) || '-09-' || substr(sold_date, 1, 2)
        WHEN sold_date LIKE '__ Oct ____' THEN
            substr(sold_date, 8, 4) || '-10-' || substr(sold_date, 1, 2)
        WHEN sold_date LIKE '__ Nov ____' THEN
            substr(sold_date, 8, 4) || '-11-' || substr(sold_date, 1, 2)
        WHEN sold_date LIKE '__ Dec ____' THEN
            substr(sold_date, 8, 4) || '-12-' || substr(sold_date, 1, 2)
        -- Single digit day format (D MMM YYYY)
        WHEN sold_date LIKE '_ Jan ____' THEN
            substr(sold_date, 7, 4) || '-01-0' || substr(sold_date, 1, 1)
        WHEN sold_date LIKE '_ Feb ____' THEN
            substr(sold_date, 7, 4) || '-02-0' || substr(sold_date, 1, 1)
        WHEN sold_date LIKE '_ Mar ____' THEN
            substr(sold_date, 7, 4) || '-03-0' || substr(sold_date, 1, 1)
        WHEN sold_date LIKE '_ Apr ____' THEN
            substr(sold_date, 7, 4) || '-04-0' || substr(sold_date, 1, 1)
        WHEN sold_date LIKE '_ May ____' THEN
            substr(sold_date, 7, 4) || '-05-0' || substr(sold_date, 1, 1)
        WHEN sold_date LIKE '_ Jun ____' THEN
            substr(sold_date, 7, 4) || '-06-0' || substr(sold_date, 1, 1)
        WHEN sold_date LIKE '_ Jul ____' THEN
            substr(sold_date, 7, 4) || '-07-0' || substr(sold_date, 1, 1)
        WHEN sold_date LIKE '_ Aug ____' THEN
            substr(sold_date, 7, 4) || '-08-0' || substr(sold_date, 1, 1)
        WHEN sold_date LIKE '_ Sep ____' THEN
            substr(sold_date, 7, 4) || '-09-0' || substr(sold_date, 1, 1)
        WHEN sold_date LIKE '_ Oct ____' THEN
            substr(sold_date, 7, 4) || '-10-0' || substr(sold_date, 1, 1)
        WHEN sold_date LIKE '_ Nov ____' THEN
            substr(sold_date, 7, 4) || '-11-0' || substr(sold_date, 1, 1)
        WHEN sold_date LIKE '_ Dec ____' THEN
            substr(sold_date, 7, 4) || '-12-0' || substr(sold_date, 1, 1)
        ELSE NULL
    END
WHERE sold_date IS NOT NULL AND sold_date_iso IS NULL;

-- Verify migration
SELECT
    'Migration complete' as status,
    COUNT(*) as total_sold,
    SUM(CASE WHEN sold_date_iso IS NOT NULL THEN 1 ELSE 0 END) as converted,
    SUM(CASE WHEN sold_date_iso IS NULL AND sold_date IS NOT NULL THEN 1 ELSE 0 END) as failed
FROM listing_history
WHERE status = 'sold';

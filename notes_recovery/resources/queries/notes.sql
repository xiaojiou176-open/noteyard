-- =============================================================================
-- Apple Notes forensic queries (macOS)
-- Schema layouts vary across macOS releases, so identify the schema first.
-- =============================================================================

-- [Step 0] Identify the schema
SELECT name, sql
FROM sqlite_master
WHERE type = 'table'
  AND (name LIKE 'ZIC%' OR name LIKE 'ZNOTE%' OR name LIKE 'ZNOTEBODY%')
ORDER BY name;

-- =============================================================================
-- [Schema A] iCloud/CloudKit layout (ZICCLOUDSYNCINGOBJECT + ZICNOTEDATA)
-- =============================================================================

-- A1. Search titles and snippets
-- Replace :keyword
SELECT
  o.Z_PK,
  o.ZIDENTIFIER,
  o.ZTITLE1,
  o.ZSNIPPET,
  o.ZMARKEDFORDELETION
FROM ZICCLOUDSYNCINGOBJECT o
WHERE (o.ZTITLE1 LIKE '%' || :keyword || '%'
   OR o.ZSNIPPET LIKE '%' || :keyword || '%')
ORDER BY o.Z_PK DESC;

-- A2. Objects already marked for deletion
SELECT
  o.Z_PK,
  o.ZIDENTIFIER,
  o.ZTITLE1,
  o.ZMARKEDFORDELETION,
  o.ZNOTEDATA,
  length(d.ZDATA) AS zdata_len
FROM ZICCLOUDSYNCINGOBJECT o
LEFT JOIN ZICNOTEDATA d ON d.Z_PK = o.ZNOTEDATA
WHERE o.ZMARKEDFORDELETION = 1
ORDER BY o.Z_PK DESC;

-- A3. Orphaned ZICNOTEDATA rows (payload exists but the parent record is gone)
SELECT
  d.Z_PK,
  length(d.ZDATA) AS zdata_len
FROM ZICNOTEDATA d
LEFT JOIN ZICCLOUDSYNCINGOBJECT o ON o.ZNOTEDATA = d.Z_PK
WHERE o.Z_PK IS NULL
ORDER BY zdata_len DESC
LIMIT 500;

-- A4. Unusually small ZDATA payloads (possible wipe or emptying candidates)
SELECT
  o.ZTITLE1,
  o.ZMARKEDFORDELETION,
  length(d.ZDATA) AS zdata_len,
  o.ZIDENTIFIER
FROM ZICCLOUDSYNCINGOBJECT o
JOIN ZICNOTEDATA d ON d.Z_PK = o.ZNOTEDATA
WHERE o.ZTITLE1 IS NOT NULL
ORDER BY zdata_len ASC
LIMIT 200;

-- =============================================================================
-- [Schema B] Legacy layout (ZNOTE + ZNOTEBODY)
-- =============================================================================

-- B1. Recently edited notes
SELECT
  n.Z_PK AS note_id,
  n.ZTITLE,
  datetime(n.ZDATEEDITED + 978307200, 'unixepoch') AS edited_utc,
  b.ZHTMLSTRING
FROM ZNOTE n
LEFT JOIN ZNOTEBODY b ON b.ZNOTE = n.Z_PK
ORDER BY n.ZDATEEDITED DESC
LIMIT 200;

-- B2. Orphaned ZNOTEBODY rows
SELECT
  b.Z_PK,
  b.ZNOTE,
  length(b.ZHTMLSTRING) AS html_len
FROM ZNOTEBODY b
LEFT JOIN ZNOTE n ON n.Z_PK = b.ZNOTE
WHERE n.Z_PK IS NULL
ORDER BY html_len DESC;

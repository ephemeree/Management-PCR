-- ─────────────────────────────────────────────────────────────────────────────
-- MIGRATION: Update corporate email addresses for live/test notification routing
-- ─────────────────────────────────────────────────────────────────────────────

-- 1. Dean Account
UPDATE tbl_auth_credentials 
SET corporate_email = 'deanacccount@gmail.com' 
WHERE corporate_email = 'sample@mail.com' OR username = 'sample@mail.com';

-- 2. WST Program Chair Account
UPDATE tbl_auth_credentials 
SET corporate_email = 'wstprogramchair@gmail.com' 
WHERE corporate_email = 'wst@mail.com' OR username = 'wst@mail.com';

-- 3. RET Chair Account
UPDATE tbl_auth_credentials 
SET corporate_email = 'corazonlopez062041@gmail.com' 
WHERE corporate_email = 'retchair@mail.com' OR username = 'retchair@mail.com';

-- 4. Designated Faculty Account
UPDATE tbl_auth_credentials 
SET corporate_email = 'mitsuhataki153@gmail.com' 
WHERE corporate_email = 'desfac@mail.com' OR username = 'desfac@mail.com';

-- Kasa database and its app login, run by the db-init service as sa on every start.
-- Safe to run again: it only creates what is missing and keeps kasa_app's password in sync
-- with KASA_APP_PASSWORD from .env.
SET NOCOUNT ON;

IF DB_ID(N'kasa') IS NULL
    CREATE DATABASE kasa;
GO

IF SUSER_ID(N'kasa_app') IS NULL
    CREATE LOGIN kasa_app WITH PASSWORD = N'$(KASA_APP_PASSWORD)', DEFAULT_DATABASE = kasa, CHECK_POLICY = ON;
ELSE
    ALTER LOGIN kasa_app WITH PASSWORD = N'$(KASA_APP_PASSWORD)';
GO

USE kasa;
GO

-- The app reads and writes rows only. It cannot change the schema; migrations run as sa.
IF USER_ID(N'kasa_app') IS NULL
    CREATE USER kasa_app FOR LOGIN kasa_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::dbo TO kasa_app;
GO

-- After the migrations: kasa_app may read the schema version but never change it.
SET NOCOUNT ON;
USE kasa;
GO
IF OBJECT_ID(N'dbo.alembic_version') IS NOT NULL
    DENY INSERT, UPDATE, DELETE ON dbo.alembic_version TO kasa_app;
GO

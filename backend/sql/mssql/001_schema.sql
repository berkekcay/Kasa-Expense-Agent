/*
  Kasa schema for SQL Server / Azure SQL (mirrors app/db/models.py).
  Run with sqlcmd or SSMS against the Kasa database (uses GO batch separators):
    sqlcmd -S <server> -d kasa -i 001_schema.sql
  Money columns are BIGINT minor units (kuruş/cents) - never FLOAT/MONEY.
*/
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

IF OBJECT_ID(N'dbo.users', N'U') IS NULL
BEGIN
CREATE TABLE dbo.users (
    id            NVARCHAR(128) NOT NULL CONSTRAINT pk_users PRIMARY KEY,  -- Firebase UID later
    display_name  NVARCHAR(100) NOT NULL,
    email         NVARCHAR(320) NULL,
    created_at    DATETIME2(0)  NOT NULL CONSTRAINT df_users_created DEFAULT SYSUTCDATETIME()
);
END;
GO

IF OBJECT_ID(N'dbo.houses', N'U') IS NULL
BEGIN
CREATE TABLE dbo.houses (
    id          INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_houses PRIMARY KEY,
    name        NVARCHAR(100) NOT NULL,
    currency    CHAR(3)       NOT NULL CONSTRAINT df_houses_currency DEFAULT 'TRY',
    created_by  NVARCHAR(128) NOT NULL CONSTRAINT fk_houses_created_by REFERENCES dbo.users(id),
    created_at  DATETIME2(0)  NOT NULL CONSTRAINT df_houses_created DEFAULT SYSUTCDATETIME()
);
END;
GO

IF OBJECT_ID(N'dbo.house_members', N'U') IS NULL
BEGIN
CREATE TABLE dbo.house_members (
    id         INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_house_members PRIMARY KEY,
    house_id   INT           NOT NULL CONSTRAINT fk_house_members_house REFERENCES dbo.houses(id),
    user_id    NVARCHAR(128) NOT NULL CONSTRAINT fk_house_members_user REFERENCES dbo.users(id),
    joined_at  DATETIME2(0)  NOT NULL CONSTRAINT df_house_members_joined DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_house_member UNIQUE (house_id, user_id)
);
CREATE INDEX ix_house_members_user ON dbo.house_members (user_id, house_id);
END;
GO

IF OBJECT_ID(N'dbo.expenses', N'U') IS NULL
BEGIN
CREATE TABLE dbo.expenses (
    id            INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_expenses PRIMARY KEY,
    owner_id      NVARCHAR(128) NOT NULL CONSTRAINT fk_expenses_owner REFERENCES dbo.users(id),  -- payer
    house_id      INT           NULL     CONSTRAINT fk_expenses_house REFERENCES dbo.houses(id),
    merchant      NVARCHAR(200) NOT NULL,
    expense_date  DATE          NOT NULL,
    currency      CHAR(3)       NOT NULL CONSTRAINT df_expenses_currency DEFAULT 'TRY',
    total_minor   BIGINT        NOT NULL CONSTRAINT ck_expenses_total_positive CHECK (total_minor > 0),
    category      NVARCHAR(50)  NULL,
    source        NVARCHAR(20)  NOT NULL CONSTRAINT df_expenses_source DEFAULT 'manual',
    note          NVARCHAR(500) NULL,
    created_at    DATETIME2(0)  NOT NULL CONSTRAINT df_expenses_created DEFAULT SYSUTCDATETIME()
);
CREATE INDEX ix_expenses_owner_date ON dbo.expenses (owner_id, expense_date DESC);
CREATE INDEX ix_expenses_house ON dbo.expenses (house_id) WHERE house_id IS NOT NULL;
END;
GO

IF OBJECT_ID(N'dbo.expense_items', N'U') IS NULL
BEGIN
CREATE TABLE dbo.expense_items (
    id            INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_expense_items PRIMARY KEY,
    expense_id    INT            NOT NULL
                  CONSTRAINT fk_expense_items_expense REFERENCES dbo.expenses(id) ON DELETE CASCADE,
    description   NVARCHAR(200)  NOT NULL,
    quantity      DECIMAL(10, 3) NOT NULL CONSTRAINT df_expense_items_qty DEFAULT 1,
    amount_minor  BIGINT         NOT NULL
);
CREATE INDEX ix_expense_items_expense ON dbo.expense_items (expense_id);
END;
GO

IF OBJECT_ID(N'dbo.expense_shares', N'U') IS NULL
BEGIN
CREATE TABLE dbo.expense_shares (
    id            INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_expense_shares PRIMARY KEY,
    expense_id    INT           NOT NULL
                  CONSTRAINT fk_expense_shares_expense REFERENCES dbo.expenses(id) ON DELETE CASCADE,
    user_id       NVARCHAR(128) NOT NULL CONSTRAINT fk_expense_shares_user REFERENCES dbo.users(id),
    amount_minor  BIGINT        NOT NULL CONSTRAINT ck_expense_shares_nonneg CHECK (amount_minor >= 0),
    CONSTRAINT uq_expense_share UNIQUE (expense_id, user_id)
);
CREATE INDEX ix_expense_shares_user ON dbo.expense_shares (user_id);
END;
GO

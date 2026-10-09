/*
  Row-level security for Kasa (SQL Server 2016+ / Azure SQL).

  The API sets the acting user on every transaction (app/db/session.py):
      EXEC sp_set_session_context @key = N'user_id', @value = <uid>;
  These policies then filter/block rows server-side, so a bug in a query (or a
  report-agent SELECT) still cannot read another user's data.

  Visibility rules
    expenses              : I paid it, or it belongs to a house I'm a member of
    expense_items/_shares : the parent expense is visible to me
    houses                : I created it or I'm a member
    house_members         : rows of houses I'm a member of (incl. my own row)
    users                 : no policy (display names only, needed to add flatmates; no money data)

  Notes
  - The app must connect as a low-privilege user (NOT db_owner / sysadmin), e.g.:
        CREATE USER kasa_app WITH PASSWORD = '<from Secret Manager>';   -- contained DB
        ALTER ROLE db_datareader ADD MEMBER kasa_app;
        ALTER ROLE db_datawriter ADD MEMBER kasa_app;
  - With no session context set (NULL), every policy hides every row.
  - house_members' predicate reads house_members itself (direct recursion). SQL Server
    detects direct recursion in predicate functions, but load-test this on the real server.
*/
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

IF SCHEMA_ID(N'security') IS NULL EXEC (N'CREATE SCHEMA security');
GO

-- Drop the policy first so the functions it is bound to can be (re)created.
IF OBJECT_ID(N'security.kasa_policy', N'SP') IS NOT NULL DROP SECURITY POLICY security.kasa_policy;
GO

CREATE OR ALTER FUNCTION security.fn_is_house_member(@house_id INT)
RETURNS TABLE
WITH SCHEMABINDING
AS RETURN
    SELECT 1 AS ok
    FROM dbo.house_members AS m
    WHERE m.house_id = @house_id
      AND m.user_id = CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(128));
GO

CREATE OR ALTER FUNCTION security.fn_expense_access(@owner_id NVARCHAR(128), @house_id INT)
RETURNS TABLE
WITH SCHEMABINDING
AS RETURN
    SELECT 1 AS ok
    WHERE @owner_id = CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(128))
       OR (@house_id IS NOT NULL AND EXISTS (
              SELECT 1 FROM dbo.house_members AS m
              WHERE m.house_id = @house_id
                AND m.user_id = CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(128))));
GO

CREATE OR ALTER FUNCTION security.fn_expense_child_access(@expense_id INT)
RETURNS TABLE
WITH SCHEMABINDING
AS RETURN
    SELECT 1 AS ok
    FROM dbo.expenses AS e
    WHERE e.id = @expense_id
      AND (e.owner_id = CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(128))
           OR (e.house_id IS NOT NULL AND EXISTS (
                  SELECT 1 FROM dbo.house_members AS m
                  WHERE m.house_id = e.house_id
                    AND m.user_id = CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(128)))));
GO

CREATE OR ALTER FUNCTION security.fn_house_access(@house_id INT, @created_by NVARCHAR(128))
RETURNS TABLE
WITH SCHEMABINDING
AS RETURN
    SELECT 1 AS ok
    WHERE @created_by = CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(128))
       OR EXISTS (
              SELECT 1 FROM dbo.house_members AS m
              WHERE m.house_id = @house_id
                AND m.user_id = CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(128)));
GO

-- A membership row may be written by an existing member adding someone else, or by the
-- house creator adding themselves right after creating it. (AFTER INSERT predicates see
-- the new row, so a self-insert must not count as "already a member".)
CREATE OR ALTER FUNCTION security.fn_member_write(@house_id INT, @user_id NVARCHAR(128))
RETURNS TABLE
WITH SCHEMABINDING
AS RETURN
    SELECT 1 AS ok
    WHERE (@user_id <> CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(128))
           AND EXISTS (
              SELECT 1 FROM dbo.house_members AS m
              WHERE m.house_id = @house_id
                AND m.user_id = CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(128))))
       OR (@user_id = CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(128))
           AND EXISTS (SELECT 1 FROM dbo.houses AS h
                       WHERE h.id = @house_id AND h.created_by = @user_id));
GO

CREATE SECURITY POLICY security.kasa_policy
    ADD FILTER PREDICATE security.fn_expense_access(owner_id, house_id) ON dbo.expenses,
    ADD BLOCK  PREDICATE security.fn_expense_access(owner_id, house_id) ON dbo.expenses AFTER INSERT,
    ADD BLOCK  PREDICATE security.fn_expense_access(owner_id, house_id) ON dbo.expenses AFTER UPDATE,

    ADD FILTER PREDICATE security.fn_expense_child_access(expense_id) ON dbo.expense_items,
    ADD BLOCK  PREDICATE security.fn_expense_child_access(expense_id) ON dbo.expense_items AFTER INSERT,
    ADD BLOCK  PREDICATE security.fn_expense_child_access(expense_id) ON dbo.expense_items AFTER UPDATE,

    ADD FILTER PREDICATE security.fn_expense_child_access(expense_id) ON dbo.expense_shares,
    ADD BLOCK  PREDICATE security.fn_expense_child_access(expense_id) ON dbo.expense_shares AFTER INSERT,
    ADD BLOCK  PREDICATE security.fn_expense_child_access(expense_id) ON dbo.expense_shares AFTER UPDATE,

    ADD FILTER PREDICATE security.fn_house_access(id, created_by) ON dbo.houses,
    ADD BLOCK  PREDICATE security.fn_house_access(id, created_by) ON dbo.houses AFTER INSERT,
    ADD BLOCK  PREDICATE security.fn_house_access(id, created_by) ON dbo.houses AFTER UPDATE,

    ADD FILTER PREDICATE security.fn_is_house_member(house_id) ON dbo.house_members,
    ADD BLOCK  PREDICATE security.fn_member_write(house_id, user_id) ON dbo.house_members AFTER INSERT
WITH (STATE = ON, SCHEMABINDING = ON);
GO

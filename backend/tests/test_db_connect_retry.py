"""Connect retry for a paused Azure SQL serverless database (no SQL Server needed)."""

import pytest
from sqlalchemy import create_engine, event

from app.db.session import (
    CONNECT_RETRY_DELAYS,
    connect_with_retry,
    describe_database,
    install_connect_retry,
    is_transient_connect_error,
)

PAUSED = (
    "HY000",
    (
        "[HY000] [Microsoft][ODBC Driver 18 for SQL Server][SQL Server]Database 'kasa' on server "
        "'kasa-sql.database.windows.net' is not currently available. Please retry the connection "
        "later. (40613) (SQLDriverConnect)"
    ),
)
BAD_LOGIN = (
    "28000",
    "[28000] [Microsoft][ODBC Driver 18 for SQL Server]Login failed for user 'kasa_app'. (18456)",
)


class FakeDbError(Exception):
    """Stands in for pyodbc.Error, which is not installed in CI."""


class FakeDialect:
    def __init__(self, errors):
        self.errors = list(errors)
        self.calls = 0

    def connect(self, *cargs, **cparams):
        self.calls += 1
        if self.errors:
            raise FakeDbError(*self.errors.pop(0))
        return ("connection", cargs, cparams)


def test_paused_database_is_retried_until_it_resumes():
    dialect, waits = FakeDialect([PAUSED, PAUSED]), []
    conn = connect_with_retry(dialect, ("dsn",), {"autocommit": False}, sleep=waits.append)
    assert conn == ("connection", ("dsn",), {"autocommit": False})
    assert dialect.calls == 3
    assert waits == list(CONNECT_RETRY_DELAYS[:2])


def test_other_errors_are_not_retried():
    dialect, waits = FakeDialect([BAD_LOGIN]), []
    with pytest.raises(Exception, match="18456"):
        connect_with_retry(dialect, (), {}, sleep=waits.append)
    assert dialect.calls == 1 and waits == []


def test_gives_up_after_the_last_delay():
    dialect, waits = FakeDialect([PAUSED] * 5), []
    with pytest.raises(Exception, match="40613"):
        connect_with_retry(dialect, (), {}, delays=(1.0, 1.0), sleep=waits.append)
    assert dialect.calls == 3 and waits == [1.0, 1.0]


def test_transient_error_codes():
    assert is_transient_connect_error(Exception(*PAUSED))
    assert is_transient_connect_error(Exception("... (40501) server is busy"))
    assert not is_transient_connect_error(Exception(*BAD_LOGIN))


def test_install_hooks_do_connect():
    engine = create_engine("sqlite://")
    listener = install_connect_retry(engine)
    assert event.contains(engine, "do_connect", listener)
    with engine.connect():  # the hook calls the dialect's normal connect
        pass
    engine.dispose()


@pytest.mark.parametrize(
    ("url", "shown", "hidden"),
    [
        ("mssql+pyodbc://kasa_app:s3cret@db:1433/kasa?driver=ODBC+Driver+18", "kasa_app:***@db", "s3cret"),
        (
            (
                "mssql+pyodbc:///?odbc_connect=DRIVER%3D%7BODBC%7D%3BSERVER%3D%28localdb%29%5CMSSQLLocalDB"
                "%3BDATABASE%3Dkasa%3BUID%3Dkasa_app%3BPWD%3Ds3cret"
            ),
            r"server=(localdb)\MSSQLLocalDB database=kasa",
            "s3cret",
        ),
        ("sqlite:///./kasa.db", "sqlite:///./kasa.db", "***"),
    ],
)
def test_describe_database_never_shows_the_password(url, shown, hidden):
    text = describe_database(url)
    assert shown in text
    assert hidden not in text

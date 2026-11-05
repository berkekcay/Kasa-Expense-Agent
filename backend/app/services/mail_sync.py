"""Purchase emails into the inbox without Google Cloud: IMAP with an app password, or an
uploaded .eml file (owner: track INGEST).

Both paths end where the Gmail API sync ends: the email-parse agent reads the message
(fenced as untrusted data) and `gmail_sync.process_messages` stores one InboxItem per email,
status pending, ignored or failed. Nothing becomes an expense until the user approves it.
Items use source "email" and external_ref "mid:<Message-ID>", so the same email arriving
twice (IMAP, then as a file) is stored once.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import MailAccount
from app.db.session import session_for
from app.integrations import imap_mail
from app.services import clock, crypto, gmail_sync
from app.services.errors import DomainError, InvalidInput, NotConfigured
from app.services.expenses import ensure_user

log = logging.getLogger(__name__)

# Known providers, so the settings form can fill the server from the address.
PROVIDERS = {
    "gmail.com": "imap.gmail.com",
    "googlemail.com": "imap.gmail.com",
    "outlook.com": "outlook.office365.com",
    "hotmail.com": "outlook.office365.com",
    "live.com": "outlook.office365.com",
    "yandex.com": "imap.yandex.com",
    "yandex.com.tr": "imap.yandex.com",
    "icloud.com": "imap.mail.me.com",
    "yahoo.com": "imap.mail.yahoo.com",
}


def guess_host(address: str) -> str | None:
    domain = address.rsplit("@", 1)[-1].strip().lower()
    return PROVIDERS.get(domain)


def get_account(db: Session, user_id: str) -> MailAccount | None:
    return db.get(MailAccount, user_id)


def _login(account: MailAccount) -> imap_mail.MailLogin:
    return imap_mail.MailLogin(
        host=account.host,
        port=account.port,
        username=account.username,
        password=crypto.decrypt(account.password_enc),
        folder=account.folder,
    )


def connect(
    db: Session,
    user_id: str,
    *,
    username: str,
    password: str,
    host: str | None = None,
    port: int = imap_mail.IMAPS_PORT,
    folder: str = "INBOX",
) -> MailAccount:
    """Check the address and password against the server, then store them (encrypted)."""
    settings = get_settings()
    if not settings.token_encryption_key:
        raise NotConfigured("TOKEN_ENCRYPTION_KEY is not set, so passwords cannot be stored")
    username = username.strip()
    password = "".join(password.split())  # Gmail shows app passwords in groups of four
    if "@" not in username or not password:
        raise InvalidInput("enter the email address and its app password")
    host = (host or guess_host(username) or "").strip().lower()
    if not host:
        raise InvalidInput("enter the IMAP server of your mail provider")
    folder = folder.strip() or "INBOX"
    imap_mail.check_server(host, port, allow_private=settings.mail_allow_private_hosts)
    login = imap_mail.MailLogin(host=host, port=port, username=username, password=password, folder=folder)
    imap_mail.check_login(login)

    ensure_user(db, user_id)
    account = get_account(db, user_id) or MailAccount(user_id=user_id)
    account.host, account.port, account.username, account.folder = host, port, username, folder
    account.password_enc = crypto.encrypt(password)
    account.uid_validity = None
    account.last_uid = None
    account.last_error = None
    db.add(account)
    db.commit()
    return account


def disconnect(db: Session, user_id: str) -> None:
    account = get_account(db, user_id)
    if account is not None:
        db.delete(account)
        db.commit()


async def sync_user(user_id: str, *, max_messages: int | None = None) -> gmail_sync.SyncResult:
    """Fetch new messages over IMAP and parse each one into the inbox."""
    from app.agents import runtime

    settings = get_settings()
    result = gmail_sync.SyncResult(user_id=user_id)
    async with gmail_sync._lock_for(f"imap:{user_id}"):
        try:
            runtime.ensure_available()
        except runtime.AgentsUnavailable as exc:
            result.error = str(exc)
            return result
        with session_for(user_id) as db:
            account = get_account(db, user_id)
            if account is None:
                result.error = "no mailbox is connected"
                return result
            try:
                login = _login(account)
            except crypto.CryptoError:
                result.error = "the stored password cannot be read; connect the mailbox again"
                return result
            except DomainError as exc:
                result.error = str(exc)
                return result
            uid_validity, after_uid = account.uid_validity, account.last_uid

        since = clock.today() - dt.timedelta(days=settings.mail_sync_days)
        try:
            fetched = await asyncio.to_thread(
                imap_mail.fetch_new,
                login,
                uid_validity=uid_validity,
                after_uid=after_uid,
                since=since,
                limit=max_messages or settings.mail_sync_max_messages,
                gmail_query=settings.gmail_query if login.host == "imap.gmail.com" else "",
            )
        except DomainError as exc:
            result.error = str(exc)
            _remember(user_id, error=result.error)
            return result

        by_id = {m.id: m for m in fetched.messages}
        complete = await gmail_sync.process_messages(user_id, list(by_id), result, by_id.__getitem__)
        _remember(
            user_id,
            uid_validity=fetched.uid_validity,
            newest_uid=fetched.newest_uid if complete else None,
            error=None if complete else "some emails could not be read; they will be tried again",
        )
    log.info(
        "imap sync %s: fetched=%d created=%d ignored=%d duplicates=%d failed=%d skipped=%d",
        user_id, result.fetched, result.created, result.ignored, result.duplicates, result.failed,
        fetched.skipped,
    )  # fmt: skip
    return result


def _remember(
    user_id: str, *, uid_validity: str | None = None, newest_uid: int | None = None, error: str | None
) -> None:
    with session_for(user_id) as db:
        account = get_account(db, user_id)
        if account is None:
            return
        if uid_validity is not None:
            if uid_validity != account.uid_validity:
                account.last_uid = None
            account.uid_validity = uid_validity
        if newest_uid is not None and (account.last_uid is None or newest_uid > account.last_uid):
            account.last_uid = newest_uid
        account.last_sync_at = dt.datetime.now(dt.UTC).replace(tzinfo=None)
        account.last_error = error[:500] if error else None
        db.commit()


async def import_file(user_id: str, raw: bytes) -> gmail_sync.SyncResult:
    """One uploaded .eml file into the inbox (the same parser and rules as a synced email)."""
    from app.agents import runtime

    if len(raw) > get_settings().mail_max_upload_bytes:
        raise InvalidInput("the email file is too large")
    if b"\n" not in raw[:4000] or b":" not in raw[:4000]:
        raise InvalidInput("this does not look like an email file (.eml)")
    runtime.ensure_available()
    message = imap_mail.parse_message(raw)
    result = gmail_sync.SyncResult(user_id=user_id)
    await gmail_sync.process_messages(user_id, [message.id], result, lambda _id: message)
    if result.failed and not result.created:
        result.error = "the email could not be read automatically; try again or add it by hand"
    return result

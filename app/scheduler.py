"""Persistent email outbox with a catch-up 10am Asia/Kolkata digest schedule."""

import logging
import os
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from app.operations import INDIA, OperationsGateway, founder_digest, rows


# Deliver configured messages once; ambiguous SMTP outcomes need manual review.
def deliver_outbox(store):
    """Deliver configured messages once; ambiguous SMTP outcomes need manual review."""
    host = os.environ.get("ELUNO_SMTP_HOST")
    if not host:
        return
    for record in rows(store, "SELECT * FROM outbox WHERE status='queued'"):
        recipient = os.environ.get(
            "ELUNO_FINANCE_EMAIL"
            if record["id"].startswith("variance-")
            else "ELUNO_FOUNDER_EMAIL"
        )
        sender = os.environ.get("ELUNO_SMTP_FROM")
        if not sender or not recipient:
            continue
        with store._connect() as connection:
            claimed = connection.execute(
                "UPDATE outbox SET status='sending' WHERE id=? AND status='queued'",
                (record["id"],),
            )
        if not claimed.rowcount:
            continue
        try:
            message = EmailMessage()
            message["From"], message["To"], message["Subject"] = (
                sender,
                recipient,
                record["subject"],
            )
            message["Message-ID"] = "<" + record["id"] + "@eluno-demo.local>"
            message.set_content(record["body"])
            with smtplib.SMTP(
                host, int(os.environ.get("ELUNO_SMTP_PORT", "587")), timeout=15
            ) as smtp:
                smtp.starttls()
                if os.environ.get("ELUNO_SMTP_USER"):
                    smtp.login(
                        os.environ["ELUNO_SMTP_USER"], os.environ["ELUNO_SMTP_PASSWORD"]
                    )
                smtp.send_message(message)
            status, error = "sent", None
        except Exception as exception:
            status, error = "delivery_uncertain", str(exception)[:300]
        with store._connect() as connection:
            connection.execute(
                "UPDATE outbox SET status=?,error=? WHERE id=?",
                (status, error, record["id"]),
            )


# Queue yesterday's report after 10am and process notifications every 30 seconds.
def scheduler_loop(stop, store_factory):
    """Queue yesterday's report after 10am and process notifications every 30 seconds."""
    while not stop.is_set():
        gateway = None
        try:
            store = store_factory()
            now = datetime.now(INDIA)
            day = (now.date() - timedelta(days=1)).isoformat()
            if now.hour >= 10 and not rows(
                store, "SELECT id FROM outbox WHERE id=?", ("digest-" + day,)
            ):
                gateway = OperationsGateway(store)
                founder_digest(store, gateway, day)
            deliver_outbox(store)
        except Exception:
            logging.getLogger(__name__).exception(
                "Scheduled report failed; will retry on the next tick"
            )
        finally:
            if gateway:
                gateway.client.close()
        stop.wait(30)

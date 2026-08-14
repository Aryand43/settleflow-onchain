import html
import re
import smtplib
import ssl
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from typing import Optional

from jinja2 import Template

from app.config import get_settings

PREVIEW_DIR = Path(__file__).resolve().parents[2] / "email_previews"

INVOICE_TEMPLATE = Template("""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Invoice {{ invoice_number }}</title></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px;">
  <h1 style="color: #1e3a5f;">Invoice from {{ merchant_name }}</h1>
  <p>Hi {{ customer_name }},</p>
  <p>Please find your invoice details below.</p>
  <table style="width: 100%; border-collapse: collapse; margin: 24px 0;">
    <tr><td><strong>Invoice</strong></td><td>{{ invoice_number }}</td></tr>
    <tr><td><strong>Amount</strong></td><td>{{ amount }} {{ currency }}</td></tr>
    <tr><td><strong>Description</strong></td><td>{{ description }}</td></tr>
    <tr><td><strong>Due date</strong></td><td>{{ due_date }}</td></tr>
  </table>
  <a href="{{ payment_url }}" style="display:inline-block;background:#2563eb;color:#fff;padding:12px 24px;text-decoration:none;border-radius:6px;">Pay Now</a>
  {% if demo_mode %}
  <p style="margin-top:24px;color:#64748b;font-size:12px;">This is a testnet demo. No real funds will be collected.</p>
  {% endif %}
</body>
</html>
""")

REMINDER_COPY = {
    "friendly": {
        "subject": "Just a quick reminder",
        "heading": "Payment Reminder",
        "body": "Hope things are going well! This is a friendly nudge that invoice "
        "<strong>{invoice_number}</strong> is <strong>{days_overdue} day(s)</strong> past its due date. "
        "No rush if it just slipped by — here's the link whenever you get a chance.",
    },
    "firm": {
        "subject": "Payment past due — action needed",
        "heading": "Payment Past Due",
        "body": "Invoice <strong>{invoice_number}</strong> is now <strong>{days_overdue} days</strong> overdue "
        "and still outstanding. Please arrange payment as soon as possible to avoid further delay.",
    },
    "final": {
        "subject": "Final notice: payment significantly overdue",
        "heading": "Final Notice",
        "body": "This is a final notice. Invoice <strong>{invoice_number}</strong> is "
        "<strong>{days_overdue} days</strong> past due. Please settle this immediately or reply to "
        "discuss a payment plan.",
    },
}

REMINDER_TEMPLATE = Template("""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{{ subject }}</title></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px;">
  <h1 style="color: #1e3a5f;">{{ heading }}</h1>
  <p>Hi {{ customer_name }},</p>
  <p>{{ body | safe }}</p>
  <p>Outstanding amount: <strong>{{ amount }} {{ currency }}</strong></p>
  <a href="{{ payment_url }}" style="display:inline-block;background:#2563eb;color:#fff;padding:12px 24px;text-decoration:none;border-radius:6px;">Pay Now</a>
  <p style="margin-top:24px;color:#94a3b8;font-size:11px;">Drafted automatically by SettleFlow's collections agent — it can only send reminders, never move funds or mark this paid.</p>
</body>
</html>
""")


@dataclass
class EmailResult:
    """What actually happened to an email.

    `delivered` is the honest bit: it is only True when an SMTP server accepted
    the message. Everything else — no SMTP configured, a send that failed —
    still writes the rendered HTML to email_previews/ so the demo keeps working
    and the activity timeline can link to what would have gone out."""

    delivered: bool
    to_email: str
    subject: str
    preview_path: Optional[str] = None
    error: Optional[str] = None

    def as_metadata(self) -> dict:
        data = {
            "delivered": self.delivered,
            "to": self.to_email,
            "subject": self.subject,
            "email_preview": self.preview_path,
        }
        if self.error:
            data["error"] = self.error
        return data


def _write_preview(kind: str, invoice_number: str, html_content: str) -> str:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_number = re.sub(r"[^A-Za-z0-9_-]", "_", invoice_number)
    path = PREVIEW_DIR / f"{stamp}_{kind}_{safe_number}.html"
    path.write_text(html_content, encoding="utf-8")
    return str(path)


def _render_invoice(**kwargs) -> str:
    settings = get_settings()
    return INVOICE_TEMPLATE.render(
        merchant_name=html.escape(kwargs["merchant_name"]),
        customer_name=html.escape(kwargs["customer_name"]),
        invoice_number=html.escape(kwargs["invoice_number"]),
        amount=kwargs["amount"],
        currency=html.escape(kwargs["currency"]),
        description=html.escape(kwargs["description"]),
        due_date=kwargs["due_date"],
        payment_url=kwargs["payment_url"],
        demo_mode=settings.demo_mode,
    )


def _render_reminder(**kwargs) -> tuple[str, str]:
    copy = REMINDER_COPY.get(kwargs["tier"], REMINDER_COPY["friendly"])
    safe_number = html.escape(kwargs["invoice_number"])
    body = copy["body"].format(
        invoice_number=safe_number, days_overdue=kwargs["days_overdue"]
    )
    rendered = REMINDER_TEMPLATE.render(
        subject=copy["subject"],
        heading=copy["heading"],
        body=body,
        customer_name=html.escape(kwargs["customer_name"]),
        amount=kwargs["amount"],
        currency=html.escape(kwargs["currency"]),
        payment_url=kwargs["payment_url"],
    )
    return copy["subject"], rendered


class PreviewEmailService:
    """Writes the rendered email to disk instead of sending it. The default,
    and what you get whenever SMTP_HOST is unset."""

    @contextmanager
    def session(self):
        """No-op, so callers can use one shape regardless of which service
        they got back from get_email_service()."""
        yield self

    def send_invoice_email(self, *, to_email: str, **kwargs) -> EmailResult:
        html_content = _render_invoice(**kwargs)
        path = _write_preview("invoice", kwargs["invoice_number"], html_content)
        return EmailResult(
            delivered=False,
            to_email=to_email,
            subject=f"Invoice {kwargs['invoice_number']} from {kwargs['merchant_name']}",
            preview_path=path,
        )

    def send_reminder_email(self, *, to_email: str, **kwargs) -> EmailResult:
        subject, html_content = _render_reminder(**kwargs)
        path = _write_preview(
            f"reminder_{kwargs['tier']}", kwargs["invoice_number"], html_content
        )
        return EmailResult(
            delivered=False, to_email=to_email, subject=subject, preview_path=path
        )


class SmtpEmailService:
    """Really sends, over SMTP.

    Provider-agnostic on purpose: Resend, Gmail, Postmark and friends all speak
    SMTP, so switching providers is an .env change rather than a code change.

    A send that fails is never silent and never fatal — the HTML still lands in
    email_previews/ and the failure is returned on the result, so the collections
    agent records what happened instead of claiming a delivery that didn't
    occur.
    """

    def __init__(self) -> None:
        # Held open only inside session(); None means "connect per message".
        self._smtp: Optional[smtplib.SMTP] = None

    @contextmanager
    def session(self):
        """Holds one connection open across many messages.

        Connecting to Gmail costs ~4 seconds — TCP, STARTTLS, then the login
        round trip — and that was being paid per email. The collections agent
        sends one per overdue invoice, so a run over five invoices spent twenty
        seconds logging in five times. Inside this block it logs in once.
        """
        settings = get_settings()
        smtp = None
        try:
            smtp = self._connect(settings)
            self._smtp = smtp
            yield self
        finally:
            self._smtp = None
            if smtp is not None:
                try:
                    smtp.quit()
                except Exception:
                    # Already closed, or the server hung up. Nothing to salvage
                    # and nothing worth failing the caller's work over.
                    pass

    def _connect(self, settings) -> smtplib.SMTP:
        if settings.smtp_starttls:
            smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
            smtp.starttls(context=ssl.create_default_context())
        else:
            smtp = smtplib.SMTP_SSL(
                settings.smtp_host,
                settings.smtp_port,
                timeout=20,
                context=ssl.create_default_context(),
            )
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password or "")
        return smtp

    def _send(self, *, to_email: str, subject: str, html_content: str) -> Optional[str]:
        """Returns None on success, or the error string on failure."""
        settings = get_settings()
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = formataddr((settings.email_from_name, settings.email_from))
        message["To"] = to_email
        message.set_content(
            "This invoice email needs an HTML-capable mail client."
        )
        message.add_alternative(html_content, subtype="html")

        try:
            if self._smtp is not None:
                self._smtp.send_message(message)
            else:
                smtp = self._connect(settings)
                try:
                    smtp.send_message(message)
                finally:
                    smtp.quit()
            return None
        except (smtplib.SMTPException, OSError) as exc:
            return f"{type(exc).__name__}: {exc}"

    def send_invoice_email(self, *, to_email: str, **kwargs) -> EmailResult:
        html_content = _render_invoice(**kwargs)
        subject = f"Invoice {kwargs['invoice_number']} from {kwargs['merchant_name']}"
        path = _write_preview("invoice", kwargs["invoice_number"], html_content)
        error = self._send(to_email=to_email, subject=subject, html_content=html_content)
        return EmailResult(
            delivered=error is None,
            to_email=to_email,
            subject=subject,
            preview_path=path,
            error=error,
        )

    def send_reminder_email(self, *, to_email: str, **kwargs) -> EmailResult:
        subject, html_content = _render_reminder(**kwargs)
        path = _write_preview(
            f"reminder_{kwargs['tier']}", kwargs["invoice_number"], html_content
        )
        error = self._send(to_email=to_email, subject=subject, html_content=html_content)
        return EmailResult(
            delivered=error is None,
            to_email=to_email,
            subject=subject,
            preview_path=path,
            error=error,
        )


def email_delivery_configured() -> bool:
    """A blank password counts as not configured.

    The .env ships with the Gmail host and address already filled in and only
    the app password missing, so requiring the password is what keeps the
    default state on preview files instead of attempting a send that is
    guaranteed to fail authentication."""
    settings = get_settings()
    return bool(settings.smtp_host and settings.email_from and settings.smtp_password)


def get_email_service():
    """SMTP when it's configured, preview files otherwise. Both halves of the
    app call this, so filling in .env switches the whole system to real
    delivery with no other change."""
    return SmtpEmailService() if email_delivery_configured() else PreviewEmailService()

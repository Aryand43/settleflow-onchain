import html
import uuid
from datetime import datetime
from pathlib import Path

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


class PreviewEmailService:
    def __init__(self) -> None:
        PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    def send_invoice_email(
        self,
        *,
        merchant_name: str,
        customer_name: str,
        invoice_number: str,
        amount: float,
        currency: str,
        description: str,
        due_date: str,
        payment_url: str,
    ) -> str:
        settings = get_settings()
        html_content = INVOICE_TEMPLATE.render(
            merchant_name=html.escape(merchant_name),
            customer_name=html.escape(customer_name),
            invoice_number=html.escape(invoice_number),
            amount=amount,
            currency=html.escape(currency),
            description=html.escape(description),
            due_date=due_date,
            payment_url=payment_url,
            demo_mode=settings.demo_mode,
        )
        filename = PREVIEW_DIR / f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_invoice_{invoice_number}.html"
        filename.write_text(html_content, encoding="utf-8")
        return str(filename)

    def send_reminder_email(
        self,
        *,
        customer_name: str,
        invoice_number: str,
        amount: float,
        currency: str,
        days_overdue: int,
        payment_url: str,
        tier: str = "friendly",
    ) -> str:
        copy = REMINDER_COPY.get(tier, REMINDER_COPY["friendly"])
        safe_invoice_number = html.escape(invoice_number)
        html_content = REMINDER_TEMPLATE.render(
            subject=copy["subject"],
            heading=copy["heading"],
            body=copy["body"].format(invoice_number=safe_invoice_number, days_overdue=days_overdue),
            customer_name=html.escape(customer_name),
            amount=amount,
            currency=html.escape(currency),
            payment_url=payment_url,
        )
        filename = (
            PREVIEW_DIR / f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_reminder_{tier}_{invoice_number}.html"
        )
        filename.write_text(html_content, encoding="utf-8")
        return str(filename)


def get_email_service() -> PreviewEmailService:
    return PreviewEmailService()

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

REMINDER_TEMPLATE = Template("""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Payment Reminder</title></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px;">
  <h1 style="color: #1e3a5f;">Payment Reminder</h1>
  <p>Hi {{ customer_name }},</p>
  <p>Your invoice <strong>{{ invoice_number }}</strong> is <strong>{{ days_overdue }} day(s)</strong> overdue.</p>
  <p>Outstanding amount: <strong>{{ amount }} {{ currency }}</strong></p>
  <a href="{{ payment_url }}" style="display:inline-block;background:#2563eb;color:#fff;padding:12px 24px;text-decoration:none;border-radius:6px;">Pay Now</a>
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
    ) -> str:
        html_content = REMINDER_TEMPLATE.render(
            customer_name=html.escape(customer_name),
            invoice_number=html.escape(invoice_number),
            amount=amount,
            currency=html.escape(currency),
            days_overdue=days_overdue,
            payment_url=payment_url,
        )
        filename = PREVIEW_DIR / f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_reminder_{invoice_number}.html"
        filename.write_text(html_content, encoding="utf-8")
        return str(filename)


def get_email_service() -> PreviewEmailService:
    return PreviewEmailService()

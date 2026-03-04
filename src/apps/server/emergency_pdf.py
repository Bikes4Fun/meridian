"""Build a printable PDF of the emergency profile. Contents are minimal for now."""

from datetime import date
from io import BytesIO
import time

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def build_pdf(profile_data=None):
    """Return PDF bytes for the emergency profile. profile_data is optional for now."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica", 24)
    c.drawString(72, height - 72, "Emergency Profile")
    c.drawString(72, height - 100, "Generated for printing.")
    c.drawString(48, height - 100, f"{date.today()}: {time.now()}")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()

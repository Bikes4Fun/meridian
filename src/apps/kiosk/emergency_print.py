"""Emergency document printing: fetch PDF, send to printer, poll job status."""

import logging
import os
import re
import subprocess
import sys
import tempfile

from kivy.clock import Clock
from kivy.metrics import dp

from .modular_display import KioskLabel, KioskButton

logger = logging.getLogger(__name__)


def _parse_lp_job_id(stdout: str) -> str | None:
    """Parse 'request id is PrinterName-123 (1 file(s))' to get PrinterName-123."""
    if not stdout:
        return None
    m = re.search(r"request id is (\S+)", stdout)
    return m.group(1) if m else None


def _job_still_queued(job_id: str) -> bool:
    """Return True if job_id still appears in lpstat -o (still queued or printing)."""
    try:
        r = subprocess.run(
            ["lpstat", "-o"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return r.returncode == 0 and job_id in (r.stdout or "")
    except Exception:
        return False


def _print_pdf_bytes(pdf_bytes: bytes) -> tuple[bool, str, str | None]:
    """Write PDF to a temp file and trigger system print. Returns (success, message, job_id)."""
    fd, path = tempfile.mkstemp(suffix=".pdf")
    try:
        os.write(fd, pdf_bytes)
        os.close(fd)
        fd = None
        job_id = None
        if sys.platform in ("darwin", "linux"):
            r = subprocess.run(["lp", path], capture_output=True, text=True, timeout=10)
            if r.returncode != 0:
                return False, r.stderr or r.stdout or "Print command failed", None
            job_id = _parse_lp_job_id(r.stdout or "")
            if job_id:
                logger.info("Print job id: %s", job_id)
        else:
            r = subprocess.run(["start", "/p", path], capture_output=True, shell=True, timeout=10)
            if r.returncode != 0:
                return False, "Print command failed", None
        msg = f"Sent to printer (job {job_id})" if job_id else "Sent to printer"
        return True, msg, job_id
    except subprocess.TimeoutExpired:
        return False, "Print timed out", None
    except Exception as e:
        return False, str(e), None
    finally:
        if fd is not None:
            os.close(fd)


def add_emergency_print_section(layout, services):
    """Add Print Emergency Document button and status label to layout. No-op if no emergency service."""
    emergency_svc = services.get("emergency_service")
    if not emergency_svc or not getattr(emergency_svc, "get_emergency_profile_pdf", None):
        return

    print_status = KioskLabel(type="caption", text="", size_hint_y=None, height=dp(36))
    poll_ev = [None]

    def _poll_job(status_label, job_id, _dt):
        if not _job_still_queued(job_id):
            status_label.text = "Print completed"
            if poll_ev[0] is not None:
                poll_ev[0].cancel()
                poll_ev[0] = None

    def _do_print(status_label, _dt):
        result = emergency_svc.get_emergency_profile_pdf()
        if not result.success:
            status_label.text = "Print failed: could not get PDF"
            return
        if not result.data:
            status_label.text = "Print failed: no PDF data"
            return
        ok, msg, job_id = _print_pdf_bytes(result.data)
        status_label.text = msg if ok else f"Print failed: {msg}"
        if ok and job_id:
            poll_ev[0] = Clock.schedule_interval(
                lambda dt: _poll_job(status_label, job_id, dt), 2.0
            )

    def _on_print(*_):
        print_status.text = "Printing..."
        Clock.schedule_once(lambda dt: _do_print(print_status, dt), 0)

    print_btn = KioskButton(
        text="Print Emergency Document",
        size_hint_y=None,
        height=dp(56),
        on_release=_on_print,
    )
    layout.add_widget(print_btn)
    layout.add_widget(print_status)

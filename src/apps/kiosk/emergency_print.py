"""Emergency document printing: fetch PDF, send to printer, poll job status."""

import logging
import os
import re
import subprocess
import sys
import tempfile

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
            r = subprocess.run(
                ["start", "/p", path], capture_output=True, shell=True, timeout=10
            )
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


def _run_emergency_print(emergency_svc, status_label=None) -> None:
    """Fetch PDF, print, update status_label if provided, schedule job polling when job_id and label."""
    if status_label is not None:
        status_label.text = "Printing..."
    result = emergency_svc.get_emergency_profile_pdf()
    if not result.success:
        if status_label is not None:
            status_label.text = "Print failed: could not get PDF"
        logger.warning("Emergency print: could not get PDF")
        return
    if not result.data:
        if status_label is not None:
            status_label.text = "Print failed: no PDF data"
        return
    ok, msg, job_id = _print_pdf_bytes(result.data)
    if status_label is not None:
        status_label.text = msg if ok else f"Print failed: {msg}"
    if ok:
        logger.info("Emergency print: %s", msg)
    else:
        logger.warning("Emergency print failed: %s", msg)


def trigger_emergency_print(services) -> None:
    """Run emergency print (e.g. when alert activated). Uses same flow and status label as the button."""
    emergency_svc = services.get("emergency_service")
    if not emergency_svc or not getattr(
        emergency_svc, "get_emergency_profile_pdf", None
    ):
        return
    status_label = services.get("_emergency_print_status_label")
    _run_emergency_print(emergency_svc, status_label)

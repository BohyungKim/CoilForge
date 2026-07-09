"""Outlook draft I/O (Windows + Outlook COM only).

Creates a pre-filled email DRAFT with the revised PDF attached and DISPLAYS it —
it never calls ``.Send()``. Mirrors ``checklist.excel_writer`` exactly: win32com
is imported lazily (so the package imports on any platform), COM is initialized
per worker thread, and the draft is opened in the user's running Outlook so John
can review and send it himself.

The recipients/body are the fixed Oxygen8 DirectCoil hand-off format John confirmed;
unresolved display names ("purchasing", "David Newton") simply show in the open draft
for him to fix.
"""
from __future__ import annotations

# Fixed body John confirmed (image #2). Signature is appended by ``_signature_html``.
BODY_HTML = (
    "<p>Good afternoon Purchasing,</p>"
    "<p>Please provide a PO for the attached quote.</p>"
    "<p>Ray, please provide revised drawings for our review and approval.</p>"
    "<p>Thank you,</p>"
)


def _signature_html() -> str:
    """John's Oxygen8 sign-off block (text form; the branded logo can be re-added
    from Outlook's own Signature button on the open draft if wanted)."""
    return (
        '<p style="margin:0"><strong>John Kim</strong><br>'
        "Mechanical Engineering Manager</p>"
        '<p style="margin:0">T 647-885-4865<br>'
        "E john@oxygen8.ca<br>W oxygen8.ca</p>"
    )


def _win32():
    try:
        import win32com.client as win32
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Outlook COM (pywin32) is required to draft the email; install pywin32"
        ) from exc
    return win32


def open_deliverable_draft(
    *,
    subject: str,
    to: str,
    cc: str | None,
    attachment_path: str | None,
    body_html: str = BODY_HTML,
) -> None:
    """Open (Display, never Send) an Outlook draft with the revised PDF attached."""
    win32 = _win32()
    import pythoncom  # part of pywin32

    com_initialized = False
    try:
        pythoncom.CoInitialize()
        com_initialized = True
    except Exception:  # noqa: BLE001 — already initialized in this thread
        pass

    try:
        # Attach to the user's running Outlook so the draft lands in their session.
        app = win32.Dispatch("Outlook.Application")
        mail = app.CreateItem(0)  # 0 = olMailItem
        mail.Subject = subject
        mail.To = to
        if cc:
            mail.CC = cc
        mail.HTMLBody = body_html + _signature_html()
        if attachment_path:
            mail.Attachments.Add(str(attachment_path))
        try:
            mail.Recipients.ResolveAll()
        except Exception:  # noqa: BLE001 — unresolved names show for John to fix
            pass
        mail.Display(False)  # open the draft — NEVER Send
    finally:
        if com_initialized:
            pythoncom.CoUninitialize()

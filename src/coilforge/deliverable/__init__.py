"""DirectCoil deliverable finalization — file the docs + draft the hand-off email.

Two layers, kept separate like the checklist feature:
- ``finalize`` — pure/filesystem: subject-name cleaning, PO-folder resolution,
  never-clobber file placement. Unit-testable without Outlook/COM.
- ``outlook_draft`` — I/O: creates a pre-filled Outlook DRAFT via win32com
  (mirrors ``checklist.excel_writer`` COM lifecycle). Never sends.

Review aid only — original source PDFs are copied, never modified; the email is
opened as a draft for John to review and send.
"""

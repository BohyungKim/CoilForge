"""Submittal corpus: a download-free index of the real submittal PDFs (the OneDrive PO
tree), the primary-submittal selection per project, and an on-disk cache of the slow
pdfplumber page extraction so canonical values re-derive in about a second.

Review aid only. Everything this package writes lives OUTSIDE the repo
(``~/CoilForgeData/submittal_index``) because it names customer projects and holds raw
submittal text; the capture ledger is only ever opened read-only.
"""

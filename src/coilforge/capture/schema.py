"""Capture-ledger schema — forward-only, additive-only migrations (1a).

Rules (enforced by tests/test_capture_ledger.py):
- Append-only DATA: no UPDATE, no DELETE, no DROP TABLE. A re-processed PDF is a
  NEW run row, never an edit of an old one.
- Forward-only migrations: only CREATE TABLE / CREATE INDEX / CREATE VIEW /
  ALTER TABLE ... ADD COLUMN ... NULL. ``PRAGMA user_version`` is the version of
  record; the ``migration`` table is the human-readable ledger.
- Derived VIEWs may be replaced (DROP VIEW is allowed) — a view carries no
  information of its own. That exception is what lets ``run_dedup`` (1d) be
  redefined later without a data migration; see the dedup note below.

Dedup note (why there is no ``dedup_key`` column):
    Route multiplicity means one PDF is observed several times (analyze ->
    checklist -> project review -> finalize each miss the workflow cache because
    ``_workflow_cache_key`` includes ``source_id``). Counting those as
    independent trials would inflate every per-rule denominator downstream.
    The fix is a dedup key — but its correct definition is NOT yet known (three
    successive drafts got it wrong in both directions). So this schema stores the
    COMPONENTS as columns and leaves the key to a VIEW (1d). Getting the
    definition wrong then costs a view swap, not a migration.
    - components that DECIDE the result: input_hash, cover_page_hint,
      product_line_hint, unit_size_hint
    - provenance labels that do NOT (kept for observability, excluded from the
      key): source_id, source_filename
    - computation identity, a DIFFERENT axis (never fold into the key, or
      COUNT(DISTINCT) degrades to COUNT(*) as the code changes): code_version,
      rules_hash, catalog_version
"""

from __future__ import annotations

CAPTURE_SCHEMA_VERSION = 1

_M1_INITIAL = (
    # Migration ledger first -- migration 1 writes its own row into it.
    """
    CREATE TABLE migration (
        version      INTEGER PRIMARY KEY,
        applied_ts   TEXT NOT NULL,
        description  TEXT NOT NULL,
        sql_sha256   TEXT NOT NULL
    )
    """,
    # The replay unit: one row per captured milestone request.
    """
    CREATE TABLE run (
        run_id                 TEXT PRIMARY KEY,
        ts_utc                 TEXT NOT NULL,
        milestone              TEXT NOT NULL,
        -- dedup COMPONENTS (see module docstring) -- the key itself is a view
        input_hash             TEXT,
        cover_page_hint        INTEGER,
        product_line_hint      TEXT,
        unit_size_hint         TEXT,
        source_id              TEXT,
        source_filename        TEXT,
        -- computation identity (a different axis; never a dedup component)
        code_version           TEXT NOT NULL,
        rules_hash             TEXT,
        catalog_version        TEXT,
        capture_schema_version INTEGER NOT NULL,
        -- project identity: recorded even when the journal deliberately drops it
        project_number         TEXT,
        project_name           TEXT,
        request_identity       TEXT,
        journal_event_id       TEXT,
        journal_error          TEXT,
        coil_count             INTEGER,
        ok                     INTEGER NOT NULL DEFAULT 1,
        error                  TEXT
    )
    """,
    "CREATE INDEX ix_run_ts ON run(ts_utc)",
    "CREATE INDEX ix_run_input ON run(input_hash)",
    "CREATE INDEX ix_run_project ON run(project_number, ts_utc)",
    "CREATE INDEX ix_run_milestone ON run(milestone)",
    # The engine input vector actually delivered for a coil (10 fields, not 21 --
    # derive_slot_values passes an explicit subset; absent == genuinely absent).
    """
    CREATE TABLE run_input (
        run_id     TEXT NOT NULL,
        coil_seq   INTEGER NOT NULL,
        key        TEXT NOT NULL,
        value_json TEXT,
        PRIMARY KEY (run_id, coil_seq, key)
    ) WITHOUT ROWID
    """,
    # One row per coil observed in a run. STABLE dimensions only -- these are the
    # enum'd axes every downstream query slices by. Evolving vocabulary goes to
    # field_observation instead.
    """
    CREATE TABLE coil (
        coil_uid            TEXT PRIMARY KEY,
        run_id              TEXT NOT NULL,
        coil_seq            INTEGER NOT NULL,
        tag                 TEXT,
        coil_category       TEXT,
        product_line        TEXT,
        terra_variant       TEXT,
        unit_size           TEXT,
        hand                TEXT,
        header_type         TEXT,
        special_feature     TEXT,
        circuits            INTEGER,
        template_id         TEXT,
        template_found      INTEGER,
        generation_allowed  INTEGER,
        drawing_value_source TEXT,
        header_engine_used  INTEGER,
        gate_flags_json     TEXT
    )
    """,
    "CREATE INDEX ix_coil_run ON coil(run_id)",
    "CREATE INDEX ix_coil_dims ON coil(product_line, unit_size, coil_category)",
    "CREATE INDEX ix_coil_tag ON coil(tag)",
    # The fact table. One row per (coil, stage, field). EAV because the field
    # vocabulary is the thing that churns and observations are sparse + multi-stage.
    # stage: slot | drawing_param | draft   (engine stage needs an engine hook -- 1c)
    """
    CREATE TABLE field_observation (
        obs_id          INTEGER PRIMARY KEY,
        run_id          TEXT NOT NULL,
        coil_uid        TEXT NOT NULL,
        stage           TEXT NOT NULL,
        field_key       TEXT NOT NULL,
        value_json      TEXT,
        value_num       REAL,
        unit            TEXT,
        source          TEXT,
        validation      TEXT,
        mode            TEXT,
        status          TEXT,
        review_required INTEGER,
        blocked_reason  TEXT,
        evidence_json   TEXT
    )
    """,
    "CREATE INDEX ix_obs_field ON field_observation(field_key, stage)",
    "CREATE INDEX ix_obs_coil ON field_observation(coil_uid)",
    "CREATE INDEX ix_obs_run ON field_observation(run_id)",
    # All comparators share checklist/compare.py::_match, so they share a table.
    """
    CREATE TABLE compare_observation (
        cmp_id     INTEGER PRIMARY KEY,
        run_id     TEXT NOT NULL,
        coil_uid   TEXT,
        coil_tag   TEXT,
        comparator TEXT NOT NULL,
        key        TEXT,
        slot       TEXT,
        label      TEXT,
        left_json  TEXT,
        right_json TEXT,
        verdict    TEXT NOT NULL
    )
    """,
    "CREATE INDEX ix_cmp ON compare_observation(comparator, key, verdict)",
    "CREATE INDEX ix_cmp_run ON compare_observation(run_id)",
    # The triage label: "did John have to look at this coil".
    """
    CREATE TABLE gate_verdict (
        run_id           TEXT NOT NULL,
        coil_uid         TEXT NOT NULL,
        verdict          TEXT NOT NULL,
        exceptions_json  TEXT,
        overrides_json   TEXT,
        PRIMARY KEY (run_id, coil_uid)
    ) WITHOUT ROWID
    """,
    # Privacy-safe pointer. Hashes only -- NEVER bytes, NEVER extracted text.
    # (test_artifact_stores_no_bytes asserts no BLOB column ever appears here.)
    """
    CREATE TABLE artifact (
        artifact_id   INTEGER PRIMARY KEY,
        run_id        TEXT NOT NULL,
        coil_uid      TEXT,
        kind          TEXT NOT NULL,
        sha256        TEXT NOT NULL,
        byte_len      INTEGER,
        page_count    INTEGER,
        filename_hash TEXT
    )
    """,
    "CREATE INDEX ix_artifact_sha ON artifact(sha256)",
    "CREATE INDEX ix_artifact_run ON artifact(run_id)",
    # The ledger's own failures. Without this, best-effort writes fail silently --
    # which is EXACTLY how four journal milestones were lost for months.
    """
    CREATE TABLE capture_error (
        err_id       INTEGER PRIMARY KEY,
        ts_utc       TEXT NOT NULL,
        run_id       TEXT,
        phase        TEXT,
        error        TEXT,
        context_json TEXT
    )
    """,
    "CREATE INDEX ix_capture_error_ts ON capture_error(ts_utc)",
)

# The correction half of the (input -> proposal -> correction) triple (1b). The
# machine's pre-override "before" value is event-sourced: the derive snapshots the
# pristine baseline into result['manual_override_events'] BEFORE Tier-B reflection
# merges the override into slot_values, and the ledger reads that snapshot (a later
# recompute would read the overridden slot and drop the correction). Older runs /
# Tier-A-only / the analyze milestone carry no snapshot and fall back to the
# override-free recompute. One row per field a human actually changed: previous ==
# machine proposal, new == the manual override, override_reason carried through.
_M2_CORRECTION = (
    """
    CREATE TABLE correction (
        correction_id       INTEGER PRIMARY KEY,
        run_id              TEXT NOT NULL,
        coil_uid            TEXT NOT NULL,
        field_key           TEXT NOT NULL,
        stage               TEXT NOT NULL,
        previous_value_json TEXT,
        previous_value_num  REAL,
        previous_mode       TEXT,
        new_value_json      TEXT,
        new_value_num       REAL,
        new_mode            TEXT,
        override_reason     TEXT,
        evidence_json       TEXT
    )
    """,
    "CREATE INDEX ix_correction_coil ON correction(coil_uid)",
    "CREATE INDEX ix_correction_field ON correction(field_key)",
    "CREATE INDEX ix_correction_run ON correction(run_id)",
)

# Engine provenance (1c). Captures WHICH rule fired + its confidence, per field, for the
# seam-A path (Tier-A-fill derive — the only wired non-frozen path that hands back the
# HeaderPrepopulateResponse). rule_firing is the per-field grain; engine_call is the
# per-invocation count summary (product/terra_variant/unit_size join to the coil table, so
# they are NOT duplicated here). No rule_snapshot yet — _SPECIAL_IDS hardcode confidence in
# Python so a YAML-declared value would mislead; rule_firing already carries the ACTUAL one.
_M3_ENGINE_PROVENANCE = (
    """
    CREATE TABLE rule_firing (
        firing_id       INTEGER PRIMARY KEY,
        run_id          TEXT NOT NULL,
        coil_uid        TEXT NOT NULL,
        field_key       TEXT NOT NULL,
        rule_id         TEXT,
        confidence      TEXT,
        review_required INTEGER,
        blocked_reason  TEXT
    )
    """,
    """
    CREATE TABLE engine_call (
        engine_call_id  INTEGER PRIMARY KEY,
        run_id          TEXT NOT NULL,
        coil_uid        TEXT NOT NULL,
        n_values        INTEGER,
        n_suggestions   INTEGER,
        n_blocked       INTEGER
    )
    """,
    "CREATE INDEX ix_rule_firing_coil ON rule_firing(coil_uid)",
    "CREATE INDEX ix_rule_firing_rule ON rule_firing(rule_id)",
    "CREATE INDEX ix_rule_firing_run ON rule_firing(run_id)",
    "CREATE INDEX ix_engine_call_run ON engine_call(run_id)",
)

# (description, statements). Index + 1 == PRAGMA user_version after it applies.
# APPEND ONLY -- never edit or remove an entry that has shipped.
MIGRATIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("initial capture ledger (1a)", _M1_INITIAL),
    ("correction table (1b)", _M2_CORRECTION),
    ("engine provenance (1c)", _M3_ENGINE_PROVENANCE),
)

def _table_exists(cr, table):
    cr.execute("SELECT to_regclass(%s) IS NOT NULL", (table,))
    return cr.fetchone()[0]


def _copy_column_if_exists(cr, table, old_column, new_column, column_type):
    """Add ``new_column`` (if missing) and copy over ``old_column``'s data
    (if it still exists) — safe to run on databases that already dropped
    the old column, that never had it (fresh installs), or where the
    table itself doesn't exist on this database (e.g. ``sale_order``/
    ``stock_picking``/``pt_transport`` only exist when l10n_pt_ao_sale/
    l10n_pt_stock — or their l10n_pt_* counterparts — are also
    installed; l10n_pt_ao on its own never creates those tables).
    Same helper/contract as l10n_pt_certificate's own
    ``migrations/1.48/pre-pt_arxi_rename_atcud.py`` (same rename wave).
    """
    if not _table_exists(cr, table):
        return
    cr.execute(
        """ALTER TABLE %s ADD COLUMN IF NOT EXISTS %s %s"""
        % (table, new_column, column_type)
    )
    cr.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = %s
            AND column_name = %s
        )
        """,
        (table, old_column),
    )
    if cr.fetchone()[0]:
        cr.execute(
            """UPDATE %s SET %s = %s WHERE %s IS NULL AND %s IS NOT NULL"""
            % (table, new_column, old_column, new_column, old_column)
        )


# Every table backed by a concrete model that inherits
# ``l10n_pt_ao.account.mixin`` and/or ``document.status.mixin`` —
# directly (``account.move``, ``account.payment``, ``sale.order``,
# ``stock.picking``) or transitively via ``at.transport.mixin``
# (``pt.transport``, in l10n_pt_stock). Confirmed against both repos
# (2026-08-28): no other model inherits either mixin.
_MIXIN_TABLES = ("account_move", "account_payment", "sale_order", "stock_picking", "pt_transport")


def migrate(cr, version):
    """Carry data over the ``pt_arxi_`` rename of several fields, so
    databases upgrading from before this rename don't silently lose
    already-recorded certification data:

    - ``l10n_pt_ao.account.mixin``: ``inalterable_hash`` ->
      ``pt_arxi_inalterable_hash``, ``validated_date`` ->
      ``pt_arxi_validated_date`` (``hash_control`` was NOT renamed —
      left alone on purpose).
    - ``document.status.mixin``: ``status_id`` -> ``pt_arxi_status_id``,
      ``status_date`` -> ``pt_arxi_status_date``.
    - ``account.move`` specifically (not part of either mixin):
      ``is_self_billing`` -> ``pt_arxi_is_self_billing``.

    Companion to l10n_pt_certificate's own
    ``migrations/1.48/pre-pt_arxi_rename_atcud.py`` (``atcud`` ->
    ``pt_arxi_atcud``, same rename wave, kept in that module since
    that's where the field is actually defined) — both use the exact
    same ``_MIXIN_TABLES`` list.
    """
    for table in _MIXIN_TABLES:
        _copy_column_if_exists(cr, table, "inalterable_hash", "pt_arxi_inalterable_hash", "VARCHAR(172)")
        _copy_column_if_exists(cr, table, "validated_date", "pt_arxi_validated_date", "TIMESTAMP")
        _copy_column_if_exists(cr, table, "status_id", "pt_arxi_status_id", "INTEGER")
        _copy_column_if_exists(cr, table, "status_date", "pt_arxi_status_date", "TIMESTAMP")

    _copy_column_if_exists(cr, "account_move", "is_self_billing", "pt_arxi_is_self_billing", "BOOLEAN")

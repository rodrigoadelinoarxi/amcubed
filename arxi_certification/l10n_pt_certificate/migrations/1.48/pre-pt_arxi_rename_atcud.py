def _table_exists(cr, table):
    cr.execute("SELECT to_regclass(%s) IS NOT NULL", (table,))
    return cr.fetchone()[0]


def _copy_column_if_exists(cr, table, old_column, new_column, column_type):
    """Add ``new_column`` (if missing) and copy over ``old_column``'s data
    (if it still exists) — safe to run on databases that already dropped
    the old column, that never had it (fresh installs), or where the
    table itself doesn't exist on this database (2026-08-28: the ATCUD
    field lives on ``l10n_pt_ao.account.mixin`` — inherited not just by
    ``account.move``/``account.payment`` but also ``sale.order``,
    ``stock.picking`` and ``pt.transport``, only reachable from
    l10n_pt_certificate transitively via l10n_pt_sale/l10n_pt_stock —
    those tables don't exist on an install that only has
    l10n_pt_certificate itself, e.g. AO-only, no PT sale/stock module).
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
# ``l10n_pt_ao.account.mixin`` (directly, or transitively via
# ``at.transport.mixin``) — see l10n_pt_ao/migrations/1.42/
# pre-pt_arxi_rename_fields.py for the sibling rename of that mixin's
# OTHER fields (inalterable_hash/validated_date/status_id/status_date),
# which uses this exact same table list.
_MIXIN_TABLES = ("account_move", "account_payment", "sale_order", "stock_picking", "pt_transport")


def migrate(cr, version):
    """Carry data over the ``pt_arxi_`` rename of ``atcud`` ->
    ``pt_arxi_atcud``, so older installations upgrading straight to this
    version don't lose the ATCUD already assigned to their certified
    documents/receipts.

    2026-08-28: originally only covered ``account_move``/
    ``account_payment`` — extended to the full table list once it came
    to light the same abstract mixin (and therefore the same rename) is
    also inherited by ``sale.order``, ``stock.picking`` and
    ``pt.transport``, which were silently losing their ATCUD on upgrade.
    """
    for table in _MIXIN_TABLES:
        _copy_column_if_exists(cr, table, "atcud", "pt_arxi_atcud", "VARCHAR")

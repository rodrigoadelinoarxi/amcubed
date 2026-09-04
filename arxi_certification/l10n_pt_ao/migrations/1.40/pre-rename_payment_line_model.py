# -*- coding: utf-8 -*-
"""Rename account.payment.line -> l10n_pt_ao.payment.line.

The generic model name ``account.payment.line`` risks colliding with any
third-party/OCA module that defines a model with that same name (it isn't
namespaced, unlike every other model this codebase owns — see
``l10n_pt_ao.account.mixin``, ``l10n_pt.account.series``, etc.). This
pre-migration renames the underlying table and registry metadata in place so
existing data survives the upgrade; the Python model itself is renamed in
the same version (models/account_payment.py).

Must run as a *pre*-migration: the table/ir_model rename has to happen
before the ORM reflects the new model name during registry loading,
otherwise Odoo would try to create a brand new (empty) table for
l10n_pt_ao.payment.line and leave the old account_payment_line table/rows
orphaned.

Idempotent: re-running finds the table/model already renamed and does
nothing (guarded by ``to_regclass``/existence checks).
"""
import logging

from odoo.tools import SQL
from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)

OLD_MODEL = "account.payment.line"
NEW_MODEL = "l10n_pt_ao.payment.line"
OLD_TABLE = "account_payment_line"
NEW_TABLE = "l10n_pt_ao_payment_line"


def migrate(cr, version):
    """Rename the account.payment.line model/table to l10n_pt_ao.payment.line.

    :param cr: database cursor
    :param version: installed module version before the upgrade (None on
        fresh installs, where there is nothing to rename)
    """
    if not version:
        return

    if not table_exists(cr, OLD_TABLE):
        _logger.info(
            "l10n_pt_ao payment line rename: table %s not found, already renamed or fresh install",
            OLD_TABLE,
        )
        return

    # 1. Table itself. Identifiers can't be bound as query parameters (a SQL
    # limitation, not psycopg2's) — SQL.identifier() safely quotes/validates
    # them instead of raw string formatting.
    cr.execute(
        SQL(
            "ALTER TABLE %s RENAME TO %s",
            SQL.identifier(OLD_TABLE),
            SQL.identifier(NEW_TABLE),
        )
    )

    # 1a. Its id sequence, purely cosmetic (the column default keeps working
    # regardless of the sequence's name, renamed anyway for tidiness).
    # to_regclass takes a plain string value (safe, not an identifier being
    # interpolated) — table_exists() doesn't apply here, it only matches
    # relkind 'r'/'v'/'m' (sequences are relkind 'S').
    cr.execute("SELECT to_regclass(%s)", (OLD_TABLE + "_id_seq",))
    if cr.fetchone()[0]:
        cr.execute(
            SQL(
                "ALTER SEQUENCE %s RENAME TO %s",
                SQL.identifier(OLD_TABLE + "_id_seq"),
                SQL.identifier(NEW_TABLE + "_id_seq"),
            )
        )

    # 2. ir_model / ir_model_fields registry rows — keep the same row (same
    # id), just point it at the new model name, so every FK from
    # ir_model_access/ir_model_data/ir_rule etc. (which reference the row by
    # id, not by name) keeps resolving correctly.
    cr.execute(
        "UPDATE ir_model SET model = %s WHERE model = %s", (NEW_MODEL, OLD_MODEL)
    )
    cr.execute(
        "UPDATE ir_model_fields SET model = %s WHERE model = %s", (NEW_MODEL, OLD_MODEL)
    )

    # 3. Rename the model's own xml_id (model_account_payment_line ->
    # model_l10n_pt_ao_payment_line) and every field xml_id
    # (field_account_payment_line__<f> -> field_l10n_pt_ao_payment_line__<f>)
    # across ALL modules that contributed fields to this model (e.g.
    # external_invoice_payments), not just l10n_pt_ao.
    old_model_underscore = OLD_MODEL.replace(".", "_")
    new_model_underscore = NEW_MODEL.replace(".", "_")
    cr.execute(
        "UPDATE ir_model_data SET name = %s WHERE model = 'ir.model' AND name = %s",
        ("model_" + new_model_underscore, "model_" + old_model_underscore),
    )
    cr.execute(
        """
        UPDATE ir_model_data
           SET name = %s || substring(name from length(%s) + 1)
         WHERE model = 'ir.model.fields'
           AND name LIKE %s
        """,
        (
            "field_" + new_model_underscore + "__",
            "field_" + old_model_underscore + "__",
            "field_" + old_model_underscore + "\\_\\_%",
        ),
    )

    # 4. Rename the access-rule xml_id to match the renamed ir.model.access.csv
    # row (access_account_payment_line -> access_l10n_pt_ao_payment_line) so
    # reloading the CSV updates the existing row instead of leaving an
    # orphan alongside a freshly-created duplicate.
    cr.execute(
        """
        UPDATE ir_model_data
           SET name = 'access_l10n_pt_ao_payment_line'
         WHERE model = 'ir.model.access'
           AND name = 'access_account_payment_line'
        """
    )

    _logger.info(
        "l10n_pt_ao payment line rename: %s -> %s (table, ir_model, ir_model_fields, xml_ids)",
        OLD_MODEL,
        NEW_MODEL,
    )

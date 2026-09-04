"""Sync the pt_arxi tax table on existing databases with the v19 update.

The accountants' 2026-07-20 tax table (187 taxes, validated against the real
v18 client databases) restructured the fuel-tax brackets and renamed the M40
self-billing codes. The template CSVs are only consumed on a fresh chart load,
so an EXISTING database (upgraded from v16/v17/v18) neither gains the new taxes
nor loses the dropped ones automatically. This post-migration, per PT company
using the ``pt_arxi`` chart:

1. CREATES the taxes that did not exist before v18 (checked against the real
   v18 databases) and are missing on this company, by loading them straight
   from the chart template (``_get_chart_template_model_data`` +
   ``_load_data``) so name/rate/code/exemption/repartition all come from the
   maintained CSV — no hand-built vals.
2. DEACTIVATES (``active = False``, never unlink) the taxes dropped from the
   table, and removes them from any fiscal-position tax mapping. They may be
   used in posted documents, so the record and its history/SAF-T must survive.

Notes:
- The withholding taxes ``ret25_b`` / ``ret25_b_tl`` and ``iva0_m99`` already
  existed in v18 (confirmed against the client databases) — they are NOT in the
  create list even though a naive CSV diff flagged them as new.
- The 14 value differences on pre-existing taxes (renamed labels, ret grouping,
  ret28_e/ret35_e IRC code) are NOT applied here: those taxes may already be
  used in documents, where ``account.tax.write`` blocks changing certified
  fields. Aligning them, if the accountants require it, needs a separate,
  document-aware step and is left out on purpose.

Idempotent: re-running creates nothing (taxes already present) and finds the
removed ones already inactive.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# Genuinely new in v19 — absent from every real v18 pt_arxi database checked
# (arxi_18_30, girt_test_18, innuos_v18_seq, leirirede_18_2, termoave_18,
# wolfcare_v18). 3 self-billing/exempt + 24 fuel-tax brackets.
NEW_TAX_XMLIDS = [
    "iva0_m40_ex",
    "iva0_m40_ic",
    "iva0_p",
    "iva23_p_gasoleo_gpl_0",
    "iva23_p_gasoleo_gpl_15",
    "iva23_p_gasoleo_gpl_2_5",
    "iva23_p_gasoleo_gpl_7_5",
    "iva23_p_gasoleo_vlphp_0",
    "iva23_p_gasoleo_vlphp_15",
    "iva23_p_gasoleo_vlphp_2_5",
    "iva23_p_gasoleo_vlphp_7_5",
    "iva23_p_gasoleo_vlpm_0",
    "iva23_p_gasoleo_vlpm_25",
    "iva23_p_gasoleo_vlpm_32",
    "iva23_p_gasoleo_vlpm_8",
    "iva23_p_gasolina_gpl_0",
    "iva23_p_gasolina_gpl_15",
    "iva23_p_gasolina_gpl_2_5",
    "iva23_p_gasolina_gpl_7_5",
    "iva23_p_gasolina_vlphp_0",
    "iva23_p_gasolina_vlphp_15",
    "iva23_p_gasolina_vlphp_2_5",
    "iva23_p_gasolina_vlphp_7_5",
    "iva23_p_gasolina_vlpm_0",
    "iva23_p_gasolina_vlpm_25",
    "iva23_p_gasolina_vlpm_32",
    "iva23_p_gasolina_vlpm_8",
]

# Dropped from the v19 table. Deactivated (not deleted) because they may be in
# posted documents / SAF-T. The old fuel brackets (_1/_2/_3) and the renamed
# M40 codes (extra/intra -> ex/ic).
REMOVED_TAX_XMLIDS = [
    "iva0_m40_extra",
    "iva0_m40_intra",
    "iva0_m44_sale",
    "iva23_p_gasoleo_gpl_1",
    "iva23_p_gasoleo_gpl_2",
    "iva23_p_gasoleo_gpl_3",
    "iva23_p_gasoleo_vlphp_1",
    "iva23_p_gasoleo_vlphp_2",
    "iva23_p_gasoleo_vlphp_3",
    "iva23_p_gasoleo_vlpm_1",
    "iva23_p_gasoleo_vlpm_2",
    "iva23_p_gasoleo_vlpm_3",
    "iva4_p_bc_ic_ma",
    "iva4_p_im_ic_ma",
    "iva4_p_s_ic_ma",
]


def _create_new_taxes(env):
    """Create the genuinely-new pt_arxi taxes on each PT company that lacks
    them, straight from the chart template."""
    companies = env["res.company"].search([("chart_template", "=", "pt_arxi")])
    total = 0
    for company in companies:
        chart = env["account.chart.template"].with_company(company)
        template_taxes = chart._get_chart_template_model_data("pt_arxi", "account.tax")
        to_create = {}
        for xmlid in NEW_TAX_XMLIDS:
            already = env.ref(f"account.{company.id}_{xmlid}", raise_if_not_found=False)
            if not already and xmlid in template_taxes:
                to_create[xmlid] = template_taxes[xmlid]
        if to_create:
            chart._load_data({"account.tax": to_create})
            total += len(to_create)
            _logger.info(
                "pt_arxi taxes: created %s new taxes on company %s",
                len(to_create),
                company.name,
            )
    return total


def _deactivate_removed_taxes(cr):
    """Deactivate the dropped taxes and clear their fiscal-position mappings."""
    like_names = tuple("%\\_" + x for x in REMOVED_TAX_XMLIDS)
    cr.execute(
        """
        SELECT res_id
          FROM ir_model_data
         WHERE model = 'account.tax'
           AND module = 'account'
           AND (%s)
        """
        % " OR ".join(["name LIKE %s"] * len(like_names)),
        like_names,
    )
    tax_ids = [row[0] for row in cr.fetchall()]
    if not tax_ids:
        return 0, 0

    # v19 dropped the account.fiscal.position.tax model: the fiscal-position
    # tax mapping is now a plain many2many (account_fiscal_position_account_tax_rel).
    cr.execute(
        """
        DELETE FROM account_fiscal_position_account_tax_rel
         WHERE account_tax_id IN %(ids)s
        """,
        {"ids": tuple(tax_ids)},
    )
    removed_maps = cr.rowcount
    cr.execute(
        "UPDATE account_tax SET active = False WHERE id IN %s",
        (tuple(tax_ids),),
    )
    return len(tax_ids), removed_maps


def migrate(cr, version):
    """Create the new pt_arxi taxes and deactivate the removed ones on existing
    databases.

    :param cr: database cursor
    :param version: installed module version before the upgrade (None on a
        fresh install, where the chart CSVs already carry the right set)
    """
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    created = _create_new_taxes(env)
    deactivated, removed_maps = _deactivate_removed_taxes(cr)
    _logger.info(
        "pt_arxi tax sync: created %s, deactivated %s (cleared %s "
        "fiscal-position mapping rows)",
        created,
        deactivated,
        removed_maps,
    )

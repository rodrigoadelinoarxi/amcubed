import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

# M35 self-billing taxes (Art.º 2.º, n.º 1, alínea j) do CIVA — verba 2.42.1).
# The taxes live in the chart template CSVs (definition in l10n_pt_certificate,
# repartition + grid tags in l10n_pt_reports_arxi). Template CSVs are only
# consumed on a fresh chart load, so this pushes them onto EXISTING pt_arxi
# companies from the template — same pattern as l10n_pt_certificate migration
# 1.46, never hand-built vals.
#
# It lives HERE (a POST migration of l10n_pt_reports_arxi), not in
# l10n_pt_certificate, on purpose: the grid tags (dp_iva[1], dp_iva[8], ...) are
# contributed by this module's @template("pt_arxi", "account.tax") function, and
# l10n_pt_reports_arxi loads AFTER l10n_pt_certificate (it depends on it). A
# migration in l10n_pt_certificate runs before this module's @template is
# registered, so it would create the taxes with EMPTY tags. Running here, after
# this module is loaded, both @template contributions are merged and the tags
# are applied. The exemption M35 itself is guaranteed by l10n_pt_certificate's
# own 1.49 migration, which has already run by now (dependency order).
M35_TAX_XMLIDS = ('iva0_m35', 'iva0_m35_sale')


def migrate(cr, version):
    if not version:
        # Fresh install: the chart load creates these from the CSV already.
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    total = 0
    for company in env['res.company'].search([('chart_template', '=', 'pt_arxi')]):
        chart = env['account.chart.template'].with_company(company)
        template_taxes = chart._get_chart_template_model_data('pt_arxi', 'account.tax')
        to_create = {}
        for xmlid in M35_TAX_XMLIDS:
            already = env.ref(f"account.{company.id}_{xmlid}", raise_if_not_found=False)
            if not already and xmlid in template_taxes:
                to_create[xmlid] = template_taxes[xmlid]
        if to_create:
            chart._load_data({'account.tax': to_create})
            total += len(to_create)
            _logger.info(
                "M35 taxes: created %s on company %s", len(to_create), company.name
            )
    _logger.info("M35 taxes: %s created across all pt_arxi companies", total)

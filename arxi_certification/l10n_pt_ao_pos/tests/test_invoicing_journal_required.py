"""UAT POS/contabilidade, ponto 2 (Paulo/Matias, 2026-08-28): "Possible
Journals" (``pos.config.invoicing_journal_ids``) is marked ``required`` on
the Settings form whenever the company has a chart of accounts, but that
``required`` view attribute is purely cosmetic — ``res.config.settings.
execute()`` never validates it (reproduced live: it saves successfully with
the field empty, no error at all). Left empty, the POS frontend
(``PaymentScreen_pt_ao.js``) silently never sets an invoicing journal on the
order — it only surfaces much later, at invoicing time, as a confusing
failure with no obvious cause. Matches both testers' reports (Paulo: had to
"choose some journal"; Matias: can't save, no indication of what's missing).

Enforced instead at ``_check_before_creating_new_session`` — the same moment
core's own similar pre-session checks (chart of accounts, pricelists,
payment methods, ...) already run — so it fails clearly at "Open Register"
instead of silently downstream.
"""
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.l10n_pt_ao.tests.test_l10n_pt_ao_common import (
    AccountTestCertifiedCommon,
)


@tagged("post_install", "-at_install")
class TestInvoicingJournalRequired(AccountTestCertifiedCommon):
    """Reuses the AO company/chart-of-accounts setup from ``l10n_pt_ao``'s
    own common test base — ``country_id in ('PT', 'AO')`` covers AO too,
    and it comes with a properly configured company (journals, chart of
    accounts) so ``pos.config.create()``'s own defaults don't trip
    unrelated core company-consistency constraints."""

    def _config(self):
        return self.env["pos.config"].create(
            {"name": "Test shop", "company_id": self.company.id}
        )

    def test_pt_ao_config_blocked_without_invoicing_journal(self):
        config = self._config()
        with self.assertRaises(ValidationError):
            config._check_invoicing_journal_ids()

    def test_pt_ao_config_passes_with_invoicing_journal(self):
        config = self._config()
        config.invoicing_journal_ids = [(6, 0, self.sale_journal.ids)]
        config._check_invoicing_journal_ids()  # must not raise

    def test_non_pt_ao_config_unaffected(self):
        """Sanity check: the requirement is PT/AO-specific, like the rest
        of this module's guards. Uses the env's own default (non-PT/AO)
        company/config — no bespoke company/chart-of-accounts setup
        needed since nothing here is actually created against it."""
        non_pt_ao_company = self.env.ref("base.main_company")
        self.assertNotIn(non_pt_ao_company.country_code, ("PT", "AO"))
        config = self.env["pos.config"].browse(
            self.env["pos.config"]
            .search([("company_id", "=", non_pt_ao_company.id)], limit=1)
            .ids
        )
        if not config:
            self.skipTest("no pre-existing non-PT/AO pos.config in this database")
        config._check_invoicing_journal_ids()  # must not raise

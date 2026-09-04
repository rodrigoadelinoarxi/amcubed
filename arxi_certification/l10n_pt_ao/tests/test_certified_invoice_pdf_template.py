"""UAT POS/contabilidade, ponto 5 (Matías, 2026-08-28): choosing "Fatura-
Recibo" and validating a POS order raised "Invalid Operation — There is no
template that applies to this move type." (native ``UserError`` from
``account.move.send._get_default_pdf_report_id``).

Root cause found live: ``account.account_invoices`` (the native fallback
report, used whenever neither the partner nor the journal has an explicit
``invoice_template_pdf_report_id``) has its ``domain`` set to
``[('journal_id.l10n_cert', '!=', True)]`` — meant to stop the plain,
non-certified report from being used on certified invoices (mirroring the
separate block already in ``ir_actions_report.py``'s ``_render_qweb_pdf``:
"You can not use this report for certified invoices"). But that left
certified journals with no fallback at all: reproduced live for a plain
certified ``out_invoice``, not just from POS.

A second, chained gap surfaced live right after fixing the first one: the
chosen fallback (``account_invoices_without_payment``) never had
``is_invoice_report`` flagged natively, which trips ``account.move.send.
_check_invoice_report()``'s own separate requirement for that flag ("The
sending of invoices is not set up properly, make sure the report used is
set for invoices."). Fixed by flagging it on the record itself
(``data/protected_reports_data.xml``) — it genuinely is an invoice report.
"""
from odoo.tests import tagged

from .test_l10n_pt_ao_common import AccountTestCertifiedCommon


@tagged("post_install", "-at_install")
class TestCertifiedInvoicePdfTemplate(AccountTestCertifiedCommon):
    """The native ``account.account_invoices`` report's ``domain`` was found,
    live, restricted to ``[('journal_id.l10n_cert', '!=', True)]`` on the
    database this UAT point was tested against — a data customization not
    tracked in any module here (so a fresh install has the native ``[]``
    domain and never hits this gap on its own). The tests reproduce that
    restriction explicitly, so the fix is exercised regardless of whether
    it happens to be present in whatever database runs the suite."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("account.account_invoices").domain = (
            "[('journal_id.l10n_cert', '!=', True)]"
        )

    def test_certified_journal_resolves_to_certified_fallback(self):
        """A certified invoice with no explicit template must resolve to
        the certified "no payment" report instead of raising."""
        move = self._create_invoice(self.sale_journal)
        self.assertTrue(self.sale_journal.l10n_cert)
        template = self.env["account.move.send"]._get_default_pdf_report_id(move)
        self.assertEqual(
            template, self.env.ref("account.account_invoices_without_payment")
        )

    def test_fallback_report_is_flagged_as_invoice_report(self):
        """The chained gap: the fallback report itself must carry
        ``is_invoice_report`` — otherwise ``_check_invoice_report()``'s own
        separate check still blocks the send/print flow even though a
        template was successfully resolved."""
        self.assertTrue(
            self.env.ref("account.account_invoices_without_payment").is_invoice_report
        )

    def test_certified_journal_passes_check_invoice_report(self):
        """End-to-end: the full native gate that raises "The sending of
        invoices is not set up properly..." must pass for a certified
        journal with no explicit template, now that both the resolved
        report and its ``is_invoice_report`` flag are in place."""
        move = self._create_invoice(self.sale_journal)
        move.action_post()
        self.env["account.move.send"]._check_invoice_report(move)  # must not raise

    def test_uncertified_journal_unaffected(self):
        """An uncertified journal is unaffected — resolves via the native
        default report as before, no change in behaviour."""
        move = self._create_invoice(self.uncertified_sale_journal)
        self.assertFalse(self.uncertified_sale_journal.l10n_cert)
        template = self.env["account.move.send"]._get_default_pdf_report_id(move)
        self.assertEqual(template, self.env.ref("account.account_invoices"))

import ast

from odoo.tests import tagged

from .test_l10n_pt_common import AccountTestPTInvoicingCommon


@tagged("post_install", "-at_install")
class TestInvoiceReportLayout(AccountTestPTInvoicingCommon):
    """``_get_name_invoice_report`` must pick the Arxi/PT layout only for
    documents that are actually certified (certified journal, or a SAF-T
    import carrying its own ``imported_hash``) — never just because the
    company is PT. See ``pdfs-certificados-plano.md`` ponto 1.
    """

    def test_certified_invoice_uses_arxi_layout(self):
        move = self._create_invoice(self.sale_journal)
        move.action_post()
        self.assertEqual(
            move._get_name_invoice_report(),
            "l10n_pt_certificate.report_invoice_document",
        )

    def test_uncertified_invoice_uses_native_layout(self):
        move = self._create_invoice(self.uncertified_sale_journal)
        move.action_post()
        self.assertNotEqual(
            move._get_name_invoice_report(),
            "l10n_pt_certificate.report_invoice_document",
        )

    def test_saft_imported_invoice_on_uncertified_journal_uses_arxi_layout(self):
        """A SAF-T import always lands on an uncertified journal
        (``source_billing='I'`` can never be certified) but must keep the
        Arxi layout since it already carries its own original hash.
        """
        move = self._create_invoice(self.uncertified_sale_journal)
        move.imported_hash = "fake-imported-hash-from-saft"
        move.action_post()
        self.assertEqual(
            move._get_name_invoice_report(),
            "l10n_pt_certificate.report_invoice_document",
        )

    def test_invoice_pdf_with_payments_hidden_on_certified_documents(self):
        """UAT 14 (Matias): the native Print menu offers two near-identical
        options on every invoice — "Invoice PDF" (with a "Paid on.../Amount
        Due" table) and "PDF without Payment" — read as confusing on a
        certified document, where the payment/paid status already has its
        own dedicated Payment Receipt report. "Invoice PDF" is hidden from
        certified documents (a domain on ``account.account_invoices``); the
        plain "PDF without Payment" stays the one available option."""
        action = self.env.ref("account.account_invoices")
        domain = ast.literal_eval(action.domain)

        cert_move = self._create_invoice(self.sale_journal)
        uncert_move = self._create_invoice(self.uncertified_sale_journal)

        self.assertNotIn(
            cert_move,
            self.env["account.move"].search(domain + [("id", "in", cert_move.ids)]),
        )
        self.assertIn(
            uncert_move,
            self.env["account.move"].search(domain + [("id", "in", uncert_move.ids)]),
        )

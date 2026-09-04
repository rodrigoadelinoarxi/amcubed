from odoo import Command
from odoo.tests import tagged

from .test_l10n_pt_common import AccountTestPTInvoicingCommon


@tagged("post_install", "-at_install")
class TestInvoiceRenderSmoke(AccountTestPTInvoicingCommon):
    """Render the actual Arxi QWeb report end-to-end for a multi-page
    invoice, to catch any template breakage from the deterministic
    ``_pt_arxi_lines_layouted()`` pagination (ponto 4) that the narrower
    unit tests in ``test_invoice_pagination.py`` wouldn't."""

    def test_multi_page_invoice_renders_without_error(self):
        self.company.pt_arxi_lines_per_page = 5
        move = self._create_invoice(self.sale_journal)
        move.invoice_line_ids = (
            [Command.clear()]
            + [
                Command.create(
                    {
                        "product_id": self.product.id,
                        "quantity": 1.0,
                        "price_unit": 10.0 + i,
                        "tax_ids": [Command.set(self.tax_sale.ids)],
                    }
                )
                for i in range(23)
            ]
            + [
                Command.create({"display_type": "line_section", "name": "Section B"}),
                Command.create(
                    {
                        "product_id": self.product.id,
                        "quantity": 1.0,
                        "price_unit": 5.0,
                        "tax_ids": [Command.set(self.tax_sale.ids)],
                    }
                ),
            ]
        )
        move.action_post()

        self.assertGreater(len(move.lines_layouted()), 1)
        # "account.account_invoices" is the native report action whose
        # template our _get_name_invoice_report()/report_invoice switch
        # redirects to l10n_pt_certificate.report_invoice_document for.
        html = self.env["ir.actions.report"]._render_qweb_html(
            "account.account_invoices", move.ids
        )[0]
        html = html.decode() if isinstance(html, bytes) else html
        self.assertIn(move.name, html)
        self.assertIn("pt_arxi_fixed_line", html)
        # The line-height marker div must wrap the cell CONTENT, not sit on
        # the <tr>/<td> — `overflow: hidden` there doesn't clip in
        # wkhtmltopdf (row height is only ever a minimum), confirmed by a
        # real printed PDF (2026-08-12). See reports.scss. It sets a
        # min-height only (NOT overflow: hidden/nowrap/ellipsis — an
        # earlier version clipped long text, caught silently cutting real
        # invoice content by a real printed PDF review, 2026-08-13, and
        # reverted — text must be free to wrap onto more lines instead).
        # Inlined directly (not just the class): every real PDF sent back
        # showed CSS living only in reports.scss never taking effect,
        # matching wkhtmltopdf failing to fetch it over HTTP during
        # conversion — the inline style has no such dependency.
        self.assertIn('<div class="pt_arxi_line_clip"', html)
        self.assertIn("min-height: 1.35rem", html)

    def test_many_lines_with_long_descriptions_render_without_error(self):
        """Stress case for the old mock+wkhtmltopdf+pdftotext mechanism:
        a document with many lines and very long descriptions was exactly
        what could desync the mock render from the real one (ponto 4's
        stated root cause). The new deterministic algorithm can't diverge
        from itself, but this still exercises the real end-to-end render
        at the company's real default ``pt_arxi_lines_per_page`` (no
        override), across many pages, with sections/notes interleaved to
        also stress the orphan-avoidance rule under load. Also pins the
        core regression this whole mechanism must never repeat: long text
        must render in full, never truncated (an earlier version clipped
        it with CSS ``overflow: hidden`` + ellipsis, caught by a real
        printed PDF review, 2026-08-13, and reverted)."""
        move = self._create_invoice(self.sale_journal)
        # Long enough to need several wrapped lines (and so weight > 1 in
        # _get_extra_line_weight()'s estimate) without dwarfing an entire
        # page's budget by itself — a single ~2000-char line did exactly
        # that (weight ~50 against a budget of 14), which is unrepresentative
        # of real content and defeats the point of a per-page budget. Kept
        # comfortably under the (now smaller, after the -2 per-page
        # "Carrying" reserve) first-page budget so it doesn't itself force
        # a preceding section header to strand alone on the previous page.
        long_description = (
            "Descrição de teste muito longa para verificar que não rebenta a "
            "paginação nem o CSS de altura fixa. " * 2
        )
        commands = [Command.clear()]
        for i in range(120):
            if i % 15 == 0:
                # Realistic (short) section title — a section/note carrying
                # the same 2000-char stress text as the product lines would
                # dominate its own page by weight alone and legitimately
                # end up last there no matter what, which isn't the
                # "orphaned heading" scenario the anti-orphan rule guards
                # against below.
                commands.append(
                    Command.create(
                        {
                            "display_type": "line_section",
                            "name": f"Secção {i // 15}",
                        }
                    )
                )
            if i % 37 == 0 and i % 15 != 0:
                # Excludes i=0, where a section AND a note would otherwise
                # land back-to-back: the documented, accepted edge case
                # (README "Known edge case") where protecting the second
                # of two adjacent headers from orphaning can itself strand
                # the first one alone on the previous page — real, but not
                # what this broad stress test is pinning.
                commands.append(
                    Command.create(
                        {
                            "display_type": "line_note",
                            "name": f"Nota longa {i}",
                        }
                    )
                )
            commands.append(
                Command.create(
                    {
                        "product_id": self.product.id,
                        "quantity": 1.0 + (i % 5),
                        "price_unit": 10.0 + i,
                        "name": f"Linha {i}: {long_description}",
                        "tax_ids": [Command.set(self.tax_sale.ids)],
                    }
                )
            )
        move.invoice_line_ids = commands
        move.action_post()

        pages = move.lines_layouted()
        self.assertGreater(len(pages), 5, "expected many pages for 120+ lines")
        # No line dropped or duplicated across pages.
        flattened_ids = sorted(line.id for page in pages for line in page)
        self.assertEqual(flattened_ids, sorted(move.invoice_line_ids.ids))
        # No section/note left as the last (orphaned) line of any page.
        for page in pages:
            if page:
                self.assertNotIn(page[-1].display_type, ("line_section", "line_note"))

        html = self.env["ir.actions.report"]._render_qweb_html(
            "account.account_invoices", move.ids
        )[0]
        html = html.decode() if isinstance(html, bytes) else html
        self.assertIn(move.name, html)
        # One <table name="invoice_line_table"> per page.
        self.assertEqual(html.count('name="invoice_line_table"'), len(pages))
        # Every long-text cell (description, section, note) got the
        # line-height marker wrapper — one per non-subtotal line rendered.
        self.assertIn('<div class="pt_arxi_line_clip"', html)
        self.assertIn("min-height: 1.35rem", html)
        # The core regression this must never repeat: the full long
        # description renders verbatim, never truncated with an ellipsis
        # (real printed PDF review, 2026-08-13 — "estás a cortar o
        # conteúdo... não pode ser"). No nowrap/ellipsis/max-width clipping
        # anywhere in the output.
        self.assertIn(f"Linha 0: {long_description}", html)
        self.assertNotIn("text-overflow: ellipsis", html)
        self.assertNotIn("white-space: nowrap; text-overflow", html)

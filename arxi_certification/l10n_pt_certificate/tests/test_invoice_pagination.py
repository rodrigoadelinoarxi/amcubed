from unittest.mock import patch

from odoo import Command
from odoo.tests import tagged

from .test_l10n_pt_common import AccountTestPTInvoicingCommon


@tagged("post_install", "-at_install")
class TestInvoicePagination(AccountTestPTInvoicingCommon):
    """``account.move.lines_layouted()`` — deterministic,
    CSS-fixed-line-height pagination (ponto 4 of ``pdfs-certificados-plano.md``),
    replacing the empirical mock-render + wkhtmltopdf + pdftotext pipeline
    for PT companies."""

    def _set_lines(self, move, count):
        """Replace ``move``'s lines with exactly ``count`` plain product
        lines (``_create_invoice`` already seeds one line — always clear
        first so tests get an exact, predictable count).

        ``name`` is set explicitly to a short, fixed string: the default
        auto-computed name ("[PROD001] Certified Test Product", 33 chars)
        measures to just over the assumed 230px description column width
        at the report's font — genuinely 2 wrapped lines, not a bug — which
        these tests' fixed weight-1-per-line assumptions don't account
        for. Explicit control keeps the fixture's intent unambiguous."""
        move.invoice_line_ids = [Command.clear()] + [
            Command.create(
                {
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": 10.0 + i,
                    "name": f"Line {i}",
                    "tax_ids": [Command.set(self.tax_sale.ids)],
                }
            )
            for i in range(count)
        ]
        return move.invoice_line_ids

    def test_all_lines_are_kept_across_pages(self):
        """No line is dropped or duplicated when splitting into pages —
        pinning the correctness "a transportar"/carried totals depend on
        (the template just sums whatever lines_layouted() hands it)."""
        self.company.pt_arxi_lines_per_page = 7  # -2 reserve -> effective 5
        self.company.pt_arxi_lines_first_page = 7
        move = self._create_invoice(self.sale_journal)
        self._set_lines(move, 12)

        pages = move.lines_layouted()
        flattened_ids = [line.id for page in pages for line in page]
        self.assertEqual(sorted(flattened_ids), sorted(move.invoice_line_ids.ids))

    def test_splits_at_configured_limit(self):
        """5 lines/page (7 configured, -2 reserve for the page's own
        "Carrying" footer row), 12 product lines -> 3 pages (5, 5, 2)."""
        self.company.pt_arxi_lines_per_page = 7
        self.company.pt_arxi_lines_first_page = 7
        move = self._create_invoice(self.sale_journal)
        self._set_lines(move, 12)

        pages = move.lines_layouted()
        self.assertEqual([len(p) for p in pages], [5, 5, 2])

    def test_bold_layout_gets_a_smaller_budget_automatically(self):
        """A single company-wide budget can't be right for both Bold
        (whose 3x-thicker decorative borders eat more vertical space than
        every other layout) and every lighter layout — tight enough for
        Bold left the others under-filling pages with blank space (real
        printed PDF, 2026-08-13 — "está com tanto espaço e tão poucas
        linhas"). Bold is auto-detected and only then gets a reduced
        budget, instead of lowering the company fields for everyone."""
        self.company.pt_arxi_lines_per_page = 18
        self.company.pt_arxi_lines_first_page = 13
        move = self._create_invoice(self.sale_journal)
        self._set_lines(move, 20)

        pages_default_layout = move.lines_layouted()

        bold_layout = self.env.ref("web.external_layout_bold", raise_if_not_found=False)
        if not bold_layout:
            self.skipTest("web.external_layout_bold not available")
        self.company.external_report_layout_id = bold_layout
        pages_bold_layout = move.lines_layouted()

        # Same content, but Bold's reduced budget fits fewer lines on the
        # first page (and thus needs at least as many pages overall).
        self.assertLess(len(pages_bold_layout[0]), len(pages_default_layout[0]))
        self.assertGreaterEqual(len(pages_bold_layout), len(pages_default_layout))

    def test_first_page_uses_its_own_smaller_budget(self):
        """The first page has less usable vertical space than later pages
        (company logo/address/customer info/title print above the table
        there) — using one budget for every page let the first page's
        table silently overflow onto an extra physical page that this
        method didn't know about, and the 'Carried' line (only shown from
        the 2nd logical page on) never printed on it (real printed PDF,
        2026-08-13)."""
        self.company.pt_arxi_lines_first_page = 5  # -2 reserve -> effective 3
        self.company.pt_arxi_lines_per_page = 7  # -2 reserve -> effective 5
        move = self._create_invoice(self.sale_journal)
        self._set_lines(move, 8)

        pages = move.lines_layouted()
        # first page capped at 3 (not 5), remaining 5 lines fit on page 2
        # (budget 5) in one page.
        self.assertEqual([len(p) for p in pages], [3, 5])

    def test_all_lines_fit_on_one_page_when_under_the_limit(self):
        move = self._create_invoice(self.sale_journal)
        self._set_lines(move, 3)

        pages = move.lines_layouted()
        self.assertEqual(len(pages), 1)
        self.assertEqual([line.id for line in pages[0]], move.invoice_line_ids.ids)

    def test_extra_line_weight_counts_as_more_than_one_slot(self):
        """A line declaring weight 3 uses 3 of the page's slots."""
        self.company.pt_arxi_lines_per_page = 7  # -2 reserve -> effective 5
        self.company.pt_arxi_lines_first_page = 7
        move = self._create_invoice(self.sale_journal)
        lines = self._set_lines(move, 4)
        heavy_line_id = lines[0].id

        AccountMoveLine = type(lines)
        original = AccountMoveLine._get_extra_line_weight

        def weighted(self):
            self.ensure_one()
            return 3 if self.id == heavy_line_id else original(self)

        # heavy_line (weight 3) + 3 normal lines (weight 1 each) = budget 5
        # -> heavy_line + 2 normal fit on page 1 (weight 5), 1 normal on page 2
        with patch.object(AccountMoveLine, "_get_extra_line_weight", weighted):
            pages = move.lines_layouted()
        self.assertEqual([len(p) for p in pages], [3, 1])

    def test_section_line_not_orphaned_at_end_of_page(self):
        """A line_section landing as the last slot of a page is pushed to
        the next page instead of printing as an orphaned heading."""
        self.company.pt_arxi_lines_per_page = 5  # -2 reserve -> effective 3
        self.company.pt_arxi_lines_first_page = 5
        move = self._create_invoice(self.sale_journal)
        # 2 product lines (fills 2 of 3 slots), then a section line that
        # would be the 3rd/last slot -> must move to the next page.
        move.invoice_line_ids = (
            [Command.clear()]
            + [
                Command.create(
                    {
                        "product_id": self.product.id,
                        "quantity": 1.0,
                        "price_unit": 10.0,
                        "name": f"Line {_i}",
                        "tax_ids": [Command.set(self.tax_sale.ids)],
                    }
                )
                for _i in range(2)
            ]
            + [
                Command.create({"display_type": "line_section", "name": "Section A"}),
                Command.create(
                    {
                        "product_id": self.product.id,
                        "quantity": 1.0,
                        "price_unit": 10.0,
                        "name": "Line 2",
                        "tax_ids": [Command.set(self.tax_sale.ids)],
                    }
                ),
            ]
        )

        pages = move.lines_layouted()
        for page in pages:
            if page and page[-1].display_type == "line_section":
                self.fail("A section line was left orphaned at the end of a page")
        # And it must still appear somewhere (not dropped).
        section_lines = [
            line
            for page in pages
            for line in page
            if line.display_type == "line_section"
        ]
        self.assertEqual(len(section_lines), 1)

    def test_extra_line_weight_estimates_from_description_length(self):
        """A short description is still weight 1; a long one that would
        wrap onto several printed lines counts as more slots — estimated
        from the report's real font metrics (no rendering), so the
        deterministic page break stays close to the real rendered height
        without ever needing to clip/truncate the text (a first version of
        this pagination mechanism did clip long descriptions with CSS
        ``overflow: hidden`` + ellipsis, silently cutting real invoice
        content — caught by a real printed PDF review, 2026-08-13, and
        reverted; text must always render in full)."""
        move = self._create_invoice(self.sale_journal)
        short_line, long_line = self._set_lines(move, 2)
        short_line.name = "Short description"
        long_line.name = "Descrição muito longa " * 20  # ~460 chars

        self.assertEqual(short_line._get_extra_line_weight(), 1)
        self.assertGreater(long_line._get_extra_line_weight(), 5)

    def test_weight_uses_real_font_metrics_not_flat_char_count(self):
        """Two descriptions of the SAME length but very different average
        glyph width ('i'/'l' vs 'M'/'W') must not get the same weight — a
        flat characters-per-line count would treat them identically and
        was exactly what made pages break too early or too late
        depending on which characters a description happened to contain
        (real printed PDF review, 2026-08-13). Real font metrics tell
        them apart."""
        AccountMoveLine = self.env["account.move.line"]
        font = AccountMoveLine._pt_arxi_get_font()
        if font is None:
            self.skipTest(
                "No system font available for measurement in this environment"
            )
        move = self._create_invoice(self.sale_journal)
        narrow_line, wide_line = self._set_lines(move, 2)
        # Same length (60 chars), very different rendered width.
        narrow_line.name = "i" * 60
        wide_line.name = "M" * 60
        self.assertEqual(len(narrow_line.name), len(wide_line.name))

        self.assertLess(
            narrow_line._get_extra_line_weight(), wide_line._get_extra_line_weight()
        )

    def test_long_description_never_truncated_in_rendered_html(self):
        """The regression this mechanism must never repeat: a long
        description renders in full in the report HTML, never cut short
        with an ellipsis, regardless of how many pagination "slots" it's
        estimated to cost."""
        self.company.pt_arxi_lines_per_page = 7  # -2 reserve -> effective 5
        self.company.pt_arxi_lines_first_page = 7
        move = self._create_invoice(self.sale_journal)
        long_description = (
            "Descrição muito longa que não pode ser cortada " * 15
        ).strip()
        move.invoice_line_ids = [Command.clear()] + [
            Command.create(
                {
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": 10.0,
                    "name": long_description,
                    "tax_ids": [Command.set(self.tax_sale.ids)],
                }
            )
        ]
        move.action_post()

        html = self.env["ir.actions.report"]._render_qweb_html(
            "account.account_invoices", move.ids
        )[0]
        html = html.decode() if isinstance(html, bytes) else html
        self.assertIn(long_description, html)
        self.assertNotIn("text-overflow: ellipsis", html)

    def test_unbreakable_long_text_does_not_push_other_columns_off(self):
        """A description with no spaces at all (one long unbroken run of
        characters — real test/dummy data, 2026-08-13) has no ordinary
        break opportunity: without `overflow-wrap: break-word`, the column
        grows to fit it (table-layout is deliberately `auto`, not
        `fixed`), squeezing every column after it off the visible page —
        confirmed by a real printed PDF where Unit Price/Taxes/Amount
        vanished entirely from a page whose description had no spaces.
        Pins the fix: the wrap style must be present so a run like this
        gets a forced break instead."""
        move = self._create_invoice(self.sale_journal)
        move.invoice_line_ids = [
            Command.clear(),
            Command.create(
                {
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": 10.0,
                    "name": "testetstetststssttestetstetststssttestetstetststssttestet"
                    * 5,
                    "tax_ids": [Command.set(self.tax_sale.ids)],
                }
            ),
        ]
        move.action_post()

        html = self.env["ir.actions.report"]._render_qweb_html(
            "account.account_invoices", move.ids
        )[0]
        html = html.decode() if isinstance(html, bytes) else html
        self.assertIn("overflow-wrap: break-word", html)
        self.assertIn("Unit Price", html)
        self.assertIn("Taxes", html)
        self.assertIn("Amount", html)

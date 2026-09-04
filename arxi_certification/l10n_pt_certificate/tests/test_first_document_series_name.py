"""Regression test (PQC ronda, ponto 2): a manually-typed series name on
the *first* document of a brand-new certified series must be honoured,
not silently discarded.

Root cause: native ``_compute_name()`` (``addons/account/models/
account_move.py``) resets ``name`` to ``False`` before publishing whenever
``_sequence_matches_date()`` (``addons/account/models/sequence_mixin.py``)
decides the name's embedded date doesn't match the document's actual date
— it parses a year/month out of the name with a generic regex built for a
year-embedded format like ``INV/2026/00001``. Wrong assumption for the
PT/AO ``DOC_CODE SERIES/NUMBER`` format, where SERIES is an arbitrary
AT-registered code with no year requirement (e.g. ``"A30"``): a series
ending in a 2-digit run right before the ``/`` gets misread as an
unrelated year, and if it doesn't match the document's real year, the
manually-chosen name is wiped and replaced with the fallback pattern
before the AT series is even auto-created from it — silently discarding
the series code the user meant to register.

Reported as "manually chosen series ignored" (PQC, video 21/08) and
reproduced from a real customer DB backup with the test string
"GRYTR657aa46" (parses as year 46/2046, mismatching a 2026 document).
"""
from odoo import fields
from odoo.tests import tagged

from .test_l10n_pt_common import AccountTestPTInvoicingCommon


@tagged("post_install", "-at_install")
class TestFirstDocumentSeriesName(AccountTestPTInvoicingCommon):

    def test_manually_typed_series_name_honoured_on_first_document(self):
        """Typing the desired series name before publishing the very
        first document of a brand-new series (no active series yet for
        this journal/document type) is the normal, supported way to pick
        that series' code — the auto-creation mechanism
        (``_get_atcud_for_move``/``_prepare_create_series``) uses exactly
        this name's prefix as the new series' ``code``. A series code
        that happens to end in a 2-digit run right before the "/" (like
        "A30") must survive unchanged."""
        move = self._create_invoice(self.sale_journal)
        move.write({"name": "FT A30/0001"})
        move.action_post()

        self.assertEqual(
            move.name,
            "FT A30/0001",
            "the manually chosen series name must not be silently discarded",
        )
        series = self.env["l10n_pt.account.series"].search(
            [
                ("invoicing_journal_id", "=", self.sale_journal.id),
                ("document_type_id", "=", self.document_type_ft.id),
                ("state", "=", "active"),
            ]
        )
        self.assertEqual(
            series.code,
            "A30",
            "the auto-created series must use the chosen code, not a fallback",
        )

    def test_subsequent_documents_follow_the_chosen_series(self):
        """Once the series is established, later documents (whose name
        starts empty, computed fresh by the system) keep incrementing
        correctly — the fix doesn't disturb the normal flow."""
        move1 = self._create_invoice(self.sale_journal)
        move1.write({"name": "FT A30/0001"})
        move1.action_post()

        move2 = self._create_invoice(self.sale_journal)
        move2.action_post()

        self.assertEqual(move2.name, "FT A30/0002")

    def test_regular_first_document_without_manual_name_unaffected(self):
        """The normal case (no manual name typed) still works exactly as
        before: the system computes the fallback year+journal-code
        pattern and auto-creates the series from it."""
        move = self._create_invoice(self.sale_journal)
        move.action_post()

        self.assertRegex(move.name, r"^FT \d{4}\w*/0001$")

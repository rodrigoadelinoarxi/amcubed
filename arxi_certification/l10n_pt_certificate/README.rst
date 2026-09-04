=====================
Portugal - Accounting
=====================

Portuguese Accounting and Invoicing
-----------------------------------

This module implements several Portuguese specific functionalities:

- Documents and their respective reports were updated:
    * Invoices
    * Payments
    * Debit Notes
    * Credit Notes
    * Suplier Debit Notes

* Certified Document Hashing

* Generation of a Standard Audit File for Tax (SAFT)

* Portuguese Chart of Accounts.

* Portuguese Taxes and Ecotaxes.

* Portuguese Fiscal Positions.

* Simplified invoices (Fatura Simplificada).

* Restricts importing invoices to certified journals.

* QR Code.

* ATCUD.

* Specific numbering sequences for different document type inside the same journal.

* Restricts editing values for taxes used in certified documents.

* Show exchange rate and document totals in both currencies for invoices in a foreign currency.

* SAF-T Import (Chart of Accounts, Taxes, Journals, Account Moves, Documents, Customers, Products).

* SAF-T Export (Invoicing, Accounting, Self-billing).

Webservice AT
-------------

To Extract the Test Certificates:

#. openssl pkcs12 -cacerts -nokeys -in TesteWebservices.pfx -out ca-cert.ca -password pass:TESTEwebservice -passin pass:TESTEwebservice
#. openssl pkcs12 -nocerts -in TesteWebservices.pfx -out private.key -password pass:TESTEwebservice -passin pass:TESTEwebservice -passout pass:TESTEwebservice
#. openssl rsa -in private.key -out "NewKeyFile.key" -passin pass:TESTEwebservice
#. cat "NewKeyFile.key" "certificate.crt" "ca-cert.ca" > PEM.pem
#. openssl pkcs12 -export -nodes -CAfile ca-cert.ca -in PEM.pem -out "test_certificate.pem"


Requirements (External Dependencies)
------------------------------------
- pycryptodome
- xmlschema
- pdftotext
- PyMuPDF (``fitz``) — required by ``l10n_pt_ao`` for the measured
  pagination engine (see "Invoice report pagination" below); this
  module's own ``__manifest__.py`` doesn't need to declare it directly
  since the import lives in ``l10n_pt_ao``, but it must be installed in
  the same environment for PT pagination to be a real measurement instead
  of the deterministic fallback.

>>> Ubuntu sudo apt install build-essential libpoppler-cpp-dev pkg-config python3-dev

>>> pip3 install pycryptodome xmlschema pdftotext pymupdf


Invoice report pagination
--------------------------

PT invoices/sale orders split across pages using a **measured** engine
(primary mechanism): the real, final document is rendered once as a
single unbroken flow, and the print engine's own real page breaks are
read directly off that PDF's real coordinates (**PyMuPDF**/``fitz``, a
dependency of ``l10n_pt_ao`` — see
``l10n_pt_ao.account.mixin._arxi_lines_layouted_measured()``) instead of
estimated. This is not an approximation of the real rendered height, it
*is* the real rendered height. An earlier version used ``pdftotext``
(plain per-physical-page text, no coordinates) with a text-fraction
heuristic; that proved unreliable when a page-group straddled two of the
probe's own physical page breaks — real (page, y) coordinates are needed
to sum a group's true accumulated height correctly across that boundary.
The two extra costs versus estimating: printing renders the document
twice (a plain-flow probe pass, then the real paginated one), and the
probe pass must use the SAME final template as the real document (not a
separate simplified mock — see ``account_move_templates.xml``'s
``report_invoice_document_probe``), because any divergence between
what's measured and what's actually printed defeats the entire point.

If the probe render fails for any reason (``lines_layouted()`` in the
mixin catches any exception from the measured engine and logs a warning),
pagination automatically falls back to the older **deterministic**,
weight-budget engine documented below — never a hard failure. Both engines
are opt-in per document model via ``_arxi_uses_measured_pagination()``/
``_arxi_uses_deterministic_pagination()``; PT companies
(``account.move`` here) and PT/AO sale orders (``l10n_pt_sale``) opt into
both, measured first.

**Contract — what must never be broken**, or the engine silently degrades
to the deterministic fallback below (a real loss of guarantee, only
visible as a log warning, easy to miss in review): see the numbered
checklist directly above ``_arxi_uses_measured_pagination()`` in
``l10n_pt_ao/models/account_mixin.py`` — it is the single source of truth
for this contract (probe must inherit the real final template; per-page
chrome like "Carried"/"Carrying" must live inside ``<thead>``/``<tfoot>``,
never a standalone ``<div>``; markers must be unique text found via
substring match; ``t-esc``/``t-out`` only for wrapped text, never
``t-field ... widget:'text'``; ``max-width`` stays on the
``.pt_arxi_line_clip`` wrapper ``<div>``, never the ``<td>``/``<table>``;
etc.). Duplicated here would only risk drifting out of sync with the code
it describes.

The remainder of this section documents the deterministic engine, which
still applies (a) as that automatic fallback, and (b) to any other model
that opts into it without the measured engine (a per-page weight budget is
cheaper to reason about for content that doesn't need a hard guarantee).
This works as a fixed contract between CSS and Python that any
customization must respect:

- Every printed line row carries the ``pt_arxi_fixed_line`` CSS class
  (``static/src/scss/reports.scss``), a marker/hook only — it does not
  clip. Text is **never clipped**: an earlier version of this used
  ``overflow: hidden`` + an ellipsis to force every row to an exactly-fixed
  height, and a real printed PDF review (2026-08-13) caught that silently
  cutting real invoice content — unacceptable regardless of how clean the
  pagination math is. Descriptions/sections/notes wrap normally, over as
  many printed lines as they need, in a ``<div class="pt_arxi_line_clip">``
  that only sets a *minimum* height, not a maximum. The table itself is at
  the default ``table-layout: auto`` — no ``<colgroup>``, no forced column
  widths, nothing layout-specific — so every report layout (Standard,
  Boxed, Bold, Striped, Bubble, Wave, Folder — all confirmed, 2026-08-13)
  decorates it exactly like it decorates any other native table.
- ``res.company.pt_arxi_lines_per_page`` (Settings, default 30) is a budget
  of "line slots" of that fixed height, applying to every page EXCEPT the
  first — see ``pt_arxi_lines_first_page`` below. The deterministic
  pagination engine itself (``_arxi_lines_layouted_deterministic()``) is
  centralized in ``l10n_pt_ao.account.mixin`` (2026-08-14, so it's shared
  code instead of duplicated per country module) and fills each page up
  to that budget, greedily, in the document's print order;
  ``account.move`` here only supplies the hooks
  (``_arxi_uses_deterministic_pagination()``, ``_arxi_pagination_lines()``,
  ``_arxi_pagination_budget()``) that opt PT companies into it and read
  these company fields. History: raised from an earlier default of 18
  (2026-08-13) after properly-styled real printed PDFs consistently
  showed continuation pages ending with most of the page still blank
  even though the weight-sum matched the (then) 18 budget exactly. A
  first attempt raised both this AND ``pt_arxi_lines_first_page`` by the
  same proportion (18/13 → 40/28) — that overflowed the first page, which
  has meaningfully less usable space than a continuation page, so this
  value is tuned independently. A second attempt raised it to 34 alone —
  still too high: a real printed PDF (2026-08-14), measured directly with
  PyMuPDF (pt coordinates, not eyeballing), showed a logical page with 11
  lines whose *measured* weight summed to exactly 34 only had real room
  for 9 of them (31 wrapped text lines) before hitting the page edge —
  the last 2 spilled onto an extra physical sheet the pagination code
  didn't know about, which repeats that table's ``<thead>``/``<tfoot>``
  (native browser table pagination) showing a stale "Carried" total from
  *before* this page's own lines were summed — a wrong number on a
  legally certified document, not just a blank-space complaint. 30 keeps
  a small safety margin below the 31 measured-safe ceiling. Raise this
  only with real printed PDF evidence, ideally measured the same way
  (real pt/px coordinates from the rendered PDF, not visual impression of
  "too much space") — the weight estimate is still an approximation
  (``table-layout: auto``, no fixed column width, see below).
- The first page uses a separate, smaller, and independently-tuned
  budget, ``res.company.pt_arxi_lines_first_page`` (default 13, NOT
  raised alongside ``pt_arxi_lines_per_page``): it has less usable space
  than later pages (company logo, address block, customer info, invoice
  title all print above the lines table there — a continuation page only
  has the company address). Using the same budget for both let the first
  page's table silently overflow onto an extra physical page this method
  didn't know about — and the "Carried" line (only shown from the 2nd
  logical page on — explicit requirement, must never show on the actual
  first page) never printed on that extra physical page (real printed
  PDF, 2026-08-13). This value has been confirmed safe (no overflow)
  across every layout tested this session; raise it only with real
  printed PDF evidence that a specific company's first-page content
  genuinely has more room than that.
- Both budgets get a further, automatic proportional reduction (~22%)
  specifically under the "Bold" report layout
  (``account.move._pt_arxi_uses_bold_layout()``): its 3x-thicker
  decorative borders (top of the header, bottom of the last row)
  measurably eat more vertical space per page than every other layout
  tested (Standard/light, Boxed, Striped, Bubble, Wave, Folder — real
  printed PDF, 2026-08-13). A single company-wide number can't be right
  for both — tight enough for Bold left every lighter layout under-filling
  its pages with blank space; auto-detecting Bold and shaving its budget
  down there instead keeps the company fields themselves calibrated for
  the common case. If a company's actual content needs different numbers
  than 34/13 even outside Bold, override the fields directly — but change
  them, and the Bold reduction factor in ``_pt_arxi_lines_layouted()``,
  only after visual validation of a real printed PDF.
- A line's weight (how many "slots" it counts as) comes from
  ``account.move.line._get_extra_line_weight()``. For a plain short line
  this is ``1``. For a description/section/note, it's **measured**: the
  text is run through the same greedy word-wrap a browser uses, against
  the real width of the report's font (``PIL.ImageFont``, a DejaVu Sans
  file at one of a few common Linux paths — see
  ``_PT_ARXI_FONT_SIZE_PX``/``_pt_arxi_get_font()`` in
  ``models/account_move_line.py``) and an assumed rendered column width
  (``_PT_ARXI_COLUMN_WIDTH_PX_DESCRIPTION``/``_FULL_WIDTH`` — must match
  the ``max-width`` set on the corresponding ``.pt_arxi_line_clip`` div in
  ``account_move_templates.xml``, see below). An earlier version counted
  characters instead: proportional fonts don't have a uniform character
  width, so a flat divisor over/under-estimated depending on which
  characters a given description happened to contain, with no single
  constant fixing it for every description (real printed PDF review,
  2026-08-13). If Pillow or none of the candidate font paths are
  available in a given environment, this falls back to the old flat
  character-count approximation rather than failing outright — degraded,
  not broken. Either way it's still an estimate, not exact, so the
  computed page break can land a line off from the true rendered height
  (validated across 7 report layouts × several stress documents,
  2026-08-13: page counts matched exactly in the large majority of cases;
  the only observed drift was a single line whose estimated text alone
  exceeded a full page's budget — content that large will always need
  more physical space than any one page offers, regardless of estimate).
  That's an acceptable imprecision (worst case, a page is a little more or
  less full than intended, or the "Carried" total is a page early/late);
  losing content is not, and the CSS has no ``overflow: hidden`` to fall
  back on anymore. A module adding content that needs more vertical room
  for a different reason (an extra image/row) must still **declare it**
  by overriding this method — call ``super()`` first to keep the
  text-wrap estimate, then add to it.
- A section/note line is never left as the last line of a page (it would
  print as an orphaned heading) — it's pushed to the next page instead.
  Known edge case: two consecutive section/note lines immediately
  followed by a heavy line can still leave the *first* of the pair alone
  on its own page — pushing the second one off to protect it can strand
  the first, and both can't be satisfied in the same break (found via
  exhaustive testing, 2026-08-13; rare, and not content loss — a heading
  alone on a page, not a corrupted one).

**Example — correct customization** (a line that needs 1 extra slot beyond
whatever the description estimate already gives it)::

    class AccountMoveLine(models.Model):
        _inherit = "account.move.line"

        def _get_extra_line_weight(self):
            self.ensure_one()
            weight = super()._get_extra_line_weight()
            if self.my_module_needs_extra_row:
                weight += 1
            return weight

There is no automatic-discovery fallback: if a customization doesn't
respect this contract, the worst case is a page break landing a line or
two off from where the content actually wraps — never lost content, and
never a corrupted page break for the rest of the document. Changing the
fixed line height in the SCSS, ``pt_arxi_lines_per_page``/
``pt_arxi_lines_first_page``, the font-size/column-width constants in
``account_move_line.py``, and the matching ``max-width`` values in
``account_move_templates.xml`` are all parts of the same estimate — change
them together, and only after visually validating a real printed PDF;
this can't be closed from source code alone.

This mechanism applies only to PT companies (``country_code == 'PT'``).
Other companies (and other l10n_pt_ao-based localizations, e.g. Angola)
keep using the base ``l10n_pt_ao.account.mixin.lines_layouted()`` — the
mock-render + ``wkhtmltopdf`` + ``pdftotext`` page-matching pipeline that
this module's ``pdftotext`` dependency still exists for.

Known Issues
------------
1. Multicompany compatibility

Missing Features
----------------
1. Withholding tax
2. Delivery slip
3. Consignment note
4. Accounting SAF-T document

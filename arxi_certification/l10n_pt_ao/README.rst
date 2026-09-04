:target: https://www.odoo.com/documentation/17.0/legal/licenses.html#odoo-apps
:alt: License: Odoo Proprietary License v1.0

==============================
Invoicing  - Portugal / Angola
==============================

* Restricts using the default “Invoices with Payments” template as a print option for certified invoices.

* Adds taxonomies to accounts.

* Shows “copy of original document” after the first document print.

* Adds carried and carry to values on multi page invoices / sale orders.

* Freezes addresses on certified documents.

* Self paid invoices.

* Rappel credit notes.

* Restricts creating credit notes without an invoice origin.

* Restricts creating credit notes with bigger values than the original invoice.

* Restricts creating invoices with lines without products.

* Restricts creating invoice lines without one VAT Tax.

* Restricts posting and invoice if the first invoice in that journal is still in a draft state.

* Restricts printing draft invoices.

* Restricts creating invoice lines with negative values (quantities, unit prices or discounts).

* Restricts creating invoices with customers without a Reference.

* Restricts creating invoice lines with products without an Internal Reference.

* Select a refund type when creating a credit note.

* Payments now have a table for invoices paid.

* Restricts creating invoices before the last invoice date.

* Show warning when trying to invoice with a future date.

* Incoming payments now have a new number field for the receipt sequence.

* Restricts setting invoices to draft when they have an inalterable hash.

* Restricts creating a payment with a value bigger than the residual amount of the invoices being paid.

* Payments now have a payment mechanism (Cash, Wire Transfer, Credit Card…).

* Payments now have a note field (register payment popup).

* Restricts creating incoming payments before the invoice date of the invoices being paid.

* Restricts creating incoming payments without origin invoices.

* Payments save information about invoices and paid amounts at the time.

* Restricts using the resequence action on certified documents.

* Show document number in the document footer.

* Lock products and customers after using them on certified documents.

* Allow printing multiple copies (company setting).

* Printing multiple copies now show the copied value (“Original”, “Duplicate”, etc…).

* When creating a new partner, the company country is now used as a default for that partner’s country.

* Restricts changing the user name after he’s posted some certified documents.

* Adds a configurable transitory account for the tax closing report.


* Restricts creating invoices with amounts above 9999999999999.99.

Installation
============

To install this module, you need to:

#. Download the module
#. Unzip to the addons path
#. Install module in Odoo Community or Enterprise

Known issues / Roadmap
======================


Credits
=======


Contributors
------------

* Nuno Silva <nuno.silva@arxi.pt>

Do not contact contributors directly about support or help with technical issues.

License
=======
Odoo Proprietary License v1.0

This software and associated files (the "Software") may only be used (executed, modified, executed after modifications) if you have purchased a valid license from the authors, typically via Odoo Apps, or if you have received a written agreement from the authors of the Software (see the COPYRIGHT file).

You may develop Odoo modules that use the Software as a library (typically by depending on it, importing it and using its resources), but without copying any source code or material from the Software. You may distribute those modules under the license of your choice, provided that this license is compatible with the terms of the Odoo Proprietary License (For example: LGPL, MIT, or proprietary licenses similar to this one).

It is forbidden to publish, distribute, sublicense, or sell copies of the Software or modified copies of the Software.

The above copyright notice and this permission notice must be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

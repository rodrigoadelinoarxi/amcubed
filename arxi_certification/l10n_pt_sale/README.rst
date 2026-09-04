:target: https://www.odoo.com/documentation/17.0/legal/licenses.html#odoo-apps
:alt: License: Odoo Proprietary License v1.0

==========================
Portugal - Certified Sales
==========================

This module implements several Portuguese specific functionalities:

- Documents and their respective reports were updated:
    * Sale Orders
    * Invoices
- Sale Order Hashing
- Standard Audit File for Tax (SAFT)

Installation
============

To install this module, you need to:

#. Download the module
#. Unzip to the addons path
#. Install module in Odoo Community or Enterprise

Sale order report pagination
=============================

Sale orders (PT and AO, certified journals) use the same **measured**
pagination engine as ``l10n_pt_certificate``'s invoices — see that
module's README ("Invoice report pagination") for the full explanation
and, most importantly, the **contract of what must never be broken**
(documented as the single source of truth right above
``_arxi_uses_measured_pagination()`` in
``l10n_pt_ao/models/account_mixin.py``). ``sale_order.py`` here only
supplies the mixin's hooks (``_arxi_pagination_probe_report()`` ->
``l10n_pt_sale.action_report_saleorder_probe``,
``_arxi_pagination_line_marker()``, ``_arxi_pagination_lines()``); the
probe template itself is ``report_saleorder_document_probe`` in
``report/sale_order_templates.xml``.

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

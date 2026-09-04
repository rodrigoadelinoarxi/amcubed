from odoo import Command, fields
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class AccountTestPTInvoicingCommon(TransactionCase):
    """Shared setup for the AT-specific field-generation tests (hash, ATCUD,
    QR code) in this module. The general certification rules (negative
    lines, missing references, locking, credit-note origin) live and are
    tested in ``l10n_pt_ao`` instead — see
    ``l10n_pt_ao/tests/test_l10n_pt_ao_common.py``.

    Mirrors the manual setup already proven in the migration ledger's
    "Etapa 0.B" gate: a PT company with ``database.is_neutralized`` +
    ``l10n_pt_at_test`` so certified series activate/hash locally instead of
    calling the AT webservice or the Arxi central server (see
    ``_pt_arxi_local_series_mode``/``_get_remote_hash``).

    Uses the generic test chart (``generic_coa``), not the real ``pt_arxi``
    one: the certification hooks under test (hashing, ATCUD, sequencing) key
    off ``journal_id.l10n_cert``/``company.country_code``/``document_type_id``,
    not off specific account codes, so the real chart isn't needed and its
    CSV-driven xmlids don't resolve cleanly inside a test transaction.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env["ir.config_parameter"].sudo().set_param("database.is_neutralized", "1")

        cls.company = cls.env["res.company"].create(
            {
                "name": "ARXI PT Test Company",
                "country_id": cls.env.ref("base.pt").id,
                "currency_id": cls.env.ref("base.EUR").id,
                "vat": "PT123456789",
                "entity_type": "S",
                "commercial_registry": "LISBOA",
                "company_registry": "123456789",
                "street": "Rua Teste, 1",
                "city": "Lisboa",
                "zip": "1000-001",
                "l10n_pt_at_test": True,
                "tax_calculation_rounding_method": "round_globally",
            }
        )
        cls.env.user.write(
            {
                "company_ids": [Command.link(cls.company.id)],
                "company_id": cls.company.id,
            }
        )
        cls.env = cls.env(
            context=dict(cls.env.context, allowed_company_ids=cls.company.ids)
        )
        cls.company = cls.company.with_env(cls.env)

        cls.env["account.chart.template"].try_loading(
            "generic_coa", company=cls.company
        )
        # generic_coa defaults account_fiscal_country_id to US regardless of
        # the company's actual country_id — country_code (used by every
        # certification hook) is related to account_fiscal_country_id, not
        # country_id, so this must be set explicitly.
        cls.company.account_fiscal_country_id = cls.env.ref("base.pt")

        cls.document_type_ft = cls.env["account.document.type"].search(
            [
                ("code", "=", "FT"),
                ("country_id", "=", cls.env.ref("base.pt").id),
                ("is_refund", "=", False),
            ],
            limit=1,
        )

        cls.sale_journal = cls.env["account.journal"].create(
            {
                "name": "Certified Sales",
                "type": "sale",
                "code": "FT",
                "company_id": cls.company.id,
                "l10n_cert": True,
                "source_billing": "P",
                "document_type_id": cls.document_type_ft.id,
                "restrict_mode_hash_table": True,
                "refund_sequence": True,
            }
        )
        cls.uncertified_sale_journal = cls.env["account.journal"].create(
            {
                "name": "Uncertified Sales",
                "type": "sale",
                "code": "UNCERT",
                "company_id": cls.company.id,
                "l10n_cert": False,
                # source_billing default 'P' means "self-billed in this system",
                # which PT/AO law requires to be certified — an uncertified
                # journal only makes sense as an import/external source ('I').
                "source_billing": "I",
            }
        )

        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Certified Test Customer",
                "ref": "CUST001",
                "country_id": cls.env.ref("base.pt").id,
                "vat": "PT980405319",
                "company_id": False,
            }
        )

        cls.tax_group = cls.env["account.tax.group"].create(
            {
                "name": "IVA 23%",
                "country_id": cls.env.ref("base.pt").id,
            }
        )
        cls.tax_sale = cls.env["account.tax"].create(
            {
                "name": "IVA 23%",
                "amount": 23.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": cls.company.id,
                "tax_group_id": cls.tax_group.id,
                "l10n_pt_tax_type": "IVA",
                "l10n_pt_tax_code": "NOR",
                "country_region": "PT",
            }
        )

        cls.product = cls.env["product.product"].create(
            {
                "name": "Certified Test Product",
                "default_code": "PROD001",
                "type": "service",
                "lst_price": 100.0,
                "taxes_id": [Command.set(cls.tax_sale.ids)],
            }
        )

    def _create_invoice(
        self, journal, partner=None, product=None, quantity=1.0, price_unit=None
    ):
        product = product or self.product
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "journal_id": journal.id,
                "partner_id": (partner or self.partner).id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "quantity": quantity,
                            "price_unit": (
                                price_unit
                                if price_unit is not None
                                else product.lst_price
                            ),
                            "tax_ids": [Command.set(self.tax_sale.ids)],
                        }
                    )
                ],
            }
        )

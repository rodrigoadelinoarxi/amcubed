from odoo import Command, fields
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class AccountTestCertifiedCommon(TransactionCase):
    """Shared setup for the general (country-agnostic) certified-document
    rules implemented in this module: negative-line/reference checks,
    partner/product locking and credit-note-origin tracing.

    Uses an AO company deliberately, with none of the ``l10n_pt_certificate``
    fields (``entity_type``, ``l10n_pt_at_test``, ``l10n_pt_tax_type``, …) —
    that module is not installed here, and the rules under test are gated on
    ``journal_id.l10n_cert`` / ``company_id.country_code in ('PT', 'AO')``,
    not on anything PT-specific. See ``l10n_pt_certificate/tests`` for the
    AT-specific field-generation tests (hash, ATCUD, QR code).

    Uses the generic test chart (``generic_coa``) for the same reason the PT
    suite does: the checks under test don't key off specific account codes.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env["ir.config_parameter"].sudo().set_param("database.is_neutralized", "1")

        cls.company = cls.env["res.company"].create(
            {
                "name": "ARXI AO Test Company",
                "country_id": cls.env.ref("base.ao").id,
                "vat": "AO123456789",
                "company_registry": "123456789",
                "street": "Rua Teste, 1",
                "city": "Luanda",
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
        cls.company.account_fiscal_country_id = cls.env.ref("base.ao")

        cls.sale_journal = cls.env["account.journal"].create(
            {
                "name": "Certified Sales",
                "type": "sale",
                "code": "FT",
                "company_id": cls.company.id,
                "l10n_cert": True,
                "source_billing": "P",
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
                "country_id": cls.env.ref("base.ao").id,
                "company_id": False,
            }
        )
        # automatic_refs ships with Auto Increment ('1') as its own default,
        # which would otherwise silently fill in the reference below — this
        # class tests the certification blocking rule (checked at posting
        # time), not automatic_refs' own reference generation, so bypass it
        # for this one fixture and leave it genuinely empty.
        cls.partner_no_ref = (
            cls.env["res.partner"]
            .with_context(skip_automatic_ref=True)
            .create(
                {
                    "name": "Customer Without Reference",
                    "country_id": cls.env.ref("base.ao").id,
                    "company_id": False,
                }
            )
        )

        cls.tax_group = cls.env["account.tax.group"].create(
            {
                "name": "Test Tax Group",
                "country_id": cls.env.ref("base.ao").id,
            }
        )
        cls.tax_sale = cls.env["account.tax"].create(
            {
                "name": "IVA 14%",
                "amount": 14.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": cls.company.id,
                "tax_group_id": cls.tax_group.id,
            }
        )

        cls.product = cls.env["product.product"].create(
            {
                "name": "Certified Test Product",
                "default_code": "PROD001",
                "type": "service",
                "lst_price": 100.0,
                "company_id": cls.company.id,
                "taxes_id": [Command.set(cls.tax_sale.ids)],
            }
        )
        cls.product_no_ref = (
            cls.env["product.product"]
            .with_context(skip_automatic_ref=True)
            .create(
                {
                    "name": "Product Without Reference",
                    "type": "service",
                    "lst_price": 50.0,
                    "company_id": cls.company.id,
                    "taxes_id": [Command.set(cls.tax_sale.ids)],
                }
            )
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

    def _create_invoice_with_negative_line(self, journal, partner=None, product=None):
        """Two-line invoice (one normal, one negative-quantity) whose total
        stays positive — isolates a negative-quantity *line* from native
        Odoo's own "negative total" block (account/models/account_move.py),
        which applies regardless of any l10n_pt_ao logic.
        """
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
                            "quantity": 3.0,
                            "price_unit": product.lst_price,
                            "tax_ids": [Command.set(self.tax_sale.ids)],
                        }
                    ),
                    Command.create(
                        {
                            "product_id": product.id,
                            "quantity": -1.0,
                            "price_unit": product.lst_price,
                            "tax_ids": [Command.set(self.tax_sale.ids)],
                        }
                    ),
                ],
            }
        )

    def _create_invoice_with_negative_price_line(
        self, journal, partner=None, product=None
    ):
        """Two-line invoice (one normal, one negative-*price*) whose total
        stays positive — isolates a negative unit price (allowed, e.g. a
        manual discount line) from the negative-*quantity*/negative-*total*
        rules, which are the only two actually forbidden.
        """
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
                            "quantity": 3.0,
                            "price_unit": product.lst_price,
                            "tax_ids": [Command.set(self.tax_sale.ids)],
                        }
                    ),
                    Command.create(
                        {
                            "product_id": product.id,
                            "quantity": 1.0,
                            "price_unit": -product.lst_price / 2,
                            "tax_ids": [Command.set(self.tax_sale.ids)],
                        }
                    ),
                ],
            }
        )

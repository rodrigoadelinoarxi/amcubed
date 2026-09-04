from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestProtectedReports(TransactionCase):
    """Certified report views/actions flagged ``protected`` (mechanism
    defined in ``l10n_pt_ao``, data marked here — see ponto 2 of
    ``pdfs-certificados-plano.md``) must resist edit/delete from anyone but
    the superuser, and leave unflagged reports untouched."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # base.group_system ("Technical Features") has full native ACL
        # (read/write/create/unlink) on ir.ui.view — needed so the test
        # actually exercises our ``_check_protected`` override, instead of
        # just tripping over the native ACL that already blocks a plain
        # internal user from touching ir.ui.view at all.
        cls.non_admin_user = cls.env["res.users"].create(
            {
                "name": "Non Admin (Technical)",
                "login": "non_admin_report_test",
                "email": "non_admin_report_test@example.com",
                "group_ids": [(6, 0, [cls.env.ref("base.group_system").id])],
            }
        )

    def test_non_superuser_blocked_from_editing_protected_view(self):
        view = self.env.ref("l10n_pt_certificate.report_invoice_document")
        with self.assertRaises(UserError):
            view.with_user(self.non_admin_user).write({"active": False})

    def test_non_superuser_blocked_from_deleting_protected_view(self):
        view = self.env.ref("l10n_pt_certificate.report_payment_inherit")
        with self.assertRaises(UserError):
            view.with_user(self.non_admin_user).unlink()

    def test_superuser_can_edit_protected_view(self):
        view = self.env.ref("l10n_pt_certificate.report_invoice_document")
        # Should not raise.
        view.write({"active": True})

    def test_unprotected_view_stays_editable(self):
        """A view without the flag is unaffected by the check — pins that
        the block is selective, not global."""
        view = self.env["ir.ui.view"].create(
            {
                "name": "Unprotected Test View",
                "model": "res.partner",
                "arch": "<data/>",
                "type": "qweb",
            }
        )
        self.assertFalse(view.protected)
        # Should not raise, even as a non-superuser.
        view.with_user(self.non_admin_user).write({"active": False})

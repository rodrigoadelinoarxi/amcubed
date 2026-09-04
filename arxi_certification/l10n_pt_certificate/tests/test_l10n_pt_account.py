from odoo.tests.common import tagged
from . import test_l10n_pt_common


@tagged('post_install', '-at_install')
class TestL10NAccountAccount(test_l10n_pt_common.AccountTestPTInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super(TestL10NAccountAccount, cls).setUpClass()

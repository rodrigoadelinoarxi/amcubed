# isort: skip_file
# Import order matters here: several models are inherited-from
# (_inherit/_name dependencies) by files imported later in this list —
# reordering alphabetically breaks model registration at load time.
from . import ir_actions_report
from . import ir_ui_view
from . import account_mixin
from . import document_address
from . import document_type
from . import document_status_mixin
from . import document_status_type
from . import account_journal
from . import tax_report_refund_type
from . import res_company
from . import account_move
from . import account_move_line
from . import account_move_send
from . import account_payment
from . import base
from . import product_product
from . import res_partner
from . import res_users
from . import payment_method_line
from . import payment_mechanism
from . import res_config_settings
from . import account_account
from . import res_currency

# Absorbed satellite modules (Bloco C da migração v19)
from . import account_move_reason
from . import account_tax_exemption
from . import print_conf_copies
from . import res_partner_company_restrict

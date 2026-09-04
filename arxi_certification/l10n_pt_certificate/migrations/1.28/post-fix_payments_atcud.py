import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Fix payments ATCUD field based on series validation code."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    doc_type = env.ref('l10n_pt_certificate.recibo')
    payments = env['account.payment'].search([
        ('payment_name', '!=', False),
        ('pt_arxi_atcud', '=', False),
        ('pt_arxi_validated_date', '=', False),
    ])

    _logger.info(f"Found {len(payments)} payments to fix.")

    for payment in payments:
        if '/' not in payment.payment_name:
            continue

        prefix = payment.payment_name.split('/')[0].split()[-1]
        series = env['l10n_pt.account.series'].search([
            ('code', '=', prefix),
            ('document_type_id', '=', doc_type.id),
            ('company_id', '=', payment.company_id.id),
            ('state', '=', 'active'),
        ])

        if series:
            payment.pt_arxi_atcud = f'{series.validation_code}-{payment.payment_name.split("/")[-1]}'
            payment.pt_arxi_validated_date = payment.move_id.pt_arxi_validated_date
            _logger.info(f"Fixed payment {payment.payment_name} pt_arxi_atcud={payment.pt_arxi_atcud} pt_arxi_validated_date={payment.pt_arxi_validated_date} company={payment.company_id.name}")

{
    'name': 'Portugal - Payment Term Discount',
    'summary': """
        Excludes shipping charges from the native early payment discount base
    """,
    'author': "ARXILEAD",
    'website': 'https://www.arxi.pt',
    'category': 'Accounting & Finance',
    'sequence': 150,
    'version': '2.0',
    # Etapa 4.1 (2026-07-14): reduzido ao delta sobre o motor nativo de early
    # payment discount (early_discount/discount_percentage/discount_days/
    # early_pay_discount_computation no account.payment.term; reconciliação
    # automática no account.payment.register). O nativo cobre tudo o que o
    # módulo antigo fazia manualmente (discount_amt/discount_taken, writeoff
    # no wizard de pagamento, contas de desconto — agora as globais da
    # empresa). Único delta sem equivalente nativo: excluir portes da base
    # do desconto (is_exclude_shipping_lines). Contas próprias por termo,
    # NC de desconto e SAF-T Settlements descartados — ver matriz no ledger.
    'installable': True,
    'license': 'OPL-1',
    'depends': ['l10n_pt_certificate'],
    'data': [
        'views/product_view.xml',
        'views/account_payment_term_view.xml',
    ]
}

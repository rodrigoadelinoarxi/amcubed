{
    'name': 'ARXI Certification Patch - Local Signing',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations/EDI',
    'summary': 'Local certificate signing for Portuguese invoices',
    'description': '''
        This module patches l10n_pt_certificate/l10n_pt_ao to enable local signing
        of documents without remote hash/certificate retrieval, while maintaining
        instance validation.

        v19 note: Etapa 2.6 of the v19 migration moved certification hashing to a
        remote-only pipeline (`_get_remote_hash`/`_get_remote_certificate`, calling
        the Arxi central server); this patch overrides those two methods (not
        `_get_private_key`, which no longer exists) to sign/authenticate locally
        instead. AO webservice certificate not embedded — falls back to remote for AO.

        Features:
        - Local RSA signing using an embedded private key
        - Maintains contract instance validation
        - Compatible with ARXI certification requirements
        - Overrides account_mixin, account_move, and at_webservice_mixin methods
    ''',
    'author': 'ARXI',
    'website': 'https://arxi.pt',
    'depends': ['l10n_pt_certificate'],
    'data': [],
    # CORRIGIDO 2026-08-19: o motivo original (dependia de l10n_pt_certificate,
    # que por sua vez estava bloqueado por l10n_pt_ao_saft/l10n_pt_ao_access
    # com 'installable': False por engano no merge 41a25a7) ja nao se aplica -
    # a Arxi entregou este modulo com 'installable': True (commit 6e30f65,
    # 2026-08-13) e os dois bloqueadores reais foram corrigidos.
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}

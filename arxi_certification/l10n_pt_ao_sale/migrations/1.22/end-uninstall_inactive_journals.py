# -*- coding: utf-8 -*-
"""Remove the l10n_pt_ao_inactive_journals module (migração v19).

The module (a single guard blocking confirmation of quotations whose accounting
journal is archived) is being retired by decision. Its code is deleted from the
repository, so any database that still has it installed would end up in an
inconsistent state ("module installed but not found on disk") and fail to boot.

This end-migration marks it ``to remove`` so Odoo's own loader performs the
uninstall cleanly at the end of the upgrade — never ``button_immediate_uninstall``,
which triggers a nested registry rebuild mid-upgrade and crashes.

It lives in l10n_pt_ao_sale because inactive_journals depends on it, so this
module is guaranteed to be loaded when the flag is set. Idempotent: on databases
where the module is already uninstalled/absent the search returns nothing.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['ir.module.module'].search([
        ('name', '=', 'l10n_pt_ao_inactive_journals'),
        ('state', 'not in', ('uninstalled', 'uninstallable')),
    ]).write({'state': 'to remove'})
from odoo.addons.payment import setup_provider, reset_payment_provider
from . import models
from . import controllers

def post_init_hook(env):
    setup_provider(env, 'eupago_mbway')


def uninstall_hook(env):
    reset_payment_provider(env, 'eupago_mbway')

def migrate(cr, version):
    """Remove l10n_pt_ao_sale_invoice_form view that no longer exists."""
    cr.execute("""
            DELETE FROM ir_ui_view
            WHERE id IN (
                SELECT res_id FROM ir_model_data
                WHERE module = 'l10n_pt_ao_sale'
                AND name = 'l10n_pt_ao_sale_invoice_form'
                AND model = 'ir.ui.view'
            )
        """)

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Update document.address records to include VAT from the partner.
    This migration updates VAT for all document_address_id references in:
    - account.move
    - account.payment
    - sale.order
    - pt.transport
    """
    _logger.info("Running l10n_pt_ao migration: updating VAT in document.address records")

    # Update VAT in document.address from account.move
    cr.execute("""
        UPDATE document_address da
        SET vat = rp.vat
        FROM account_move am
        JOIN res_partner rp ON am.partner_id = rp.id
        WHERE da.id = am.document_address_id
        AND rp.vat IS NOT NULL
        AND (da.vat IS NULL OR da.vat = '')
    """)
    move_count = cr.rowcount
    _logger.info(f"Updated {move_count} document.address records from account.move")

    # Update VAT in document.address from account.payment
    cr.execute("""
        UPDATE document_address da
        SET vat = rp.vat
        FROM account_payment ap
        JOIN res_partner rp ON ap.partner_id = rp.id
        WHERE da.id = ap.document_address_id
        AND rp.vat IS NOT NULL
        AND (da.vat IS NULL OR da.vat = '')
    """)
    payment_count = cr.rowcount
    _logger.info(f"Updated {payment_count} document.address records from account.payment")

    # Update VAT in document.address from sale.order
    cr.execute("""
        UPDATE document_address da
        SET vat = rp.vat
        FROM sale_order so
        JOIN res_partner rp ON so.partner_id = rp.id
        WHERE da.id = so.document_address_id
        AND rp.vat IS NOT NULL
        AND (da.vat IS NULL OR da.vat = '')
    """)
    sale_count = cr.rowcount
    _logger.info(f"Updated {sale_count} document.address records from sale.order")

    # Update VAT in document.address from pt.transport (if field exists)
    # Check if pt_transport table and document_address_id column exist
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'pt_transport'
        )
    """)
    pt_transport_exists = cr.fetchone()[0]

    transport_count = 0
    if pt_transport_exists:
        cr.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'pt_transport'
                AND column_name = 'document_address_id'
            )
        """)
        field_exists = cr.fetchone()[0]

        if field_exists:
            cr.execute("""
                UPDATE document_address da
                SET vat = rp.vat
                FROM pt_transport pt
                JOIN res_partner rp ON pt.partner_id = rp.id
                WHERE da.id = pt.document_address_id
                AND rp.vat IS NOT NULL
                AND (da.vat IS NULL OR da.vat = '')
            """)
            transport_count = cr.rowcount
            _logger.info(f"Updated {transport_count} document.address records from pt.transport")
        else:
            _logger.info("pt.transport.document_address_id field not found, skipping pt.transport VAT update")
    else:
        _logger.info("pt_transport table not found, skipping pt.transport VAT update")

    total_updated = move_count + payment_count + sale_count + transport_count
    _logger.info(f"Total document.address records updated with VAT: {total_updated}")

    _logger.info("Finished l10n_pt_ao migration")

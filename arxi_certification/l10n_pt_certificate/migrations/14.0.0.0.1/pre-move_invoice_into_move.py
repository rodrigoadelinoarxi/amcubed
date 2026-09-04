def migrate(cr, version):
    cr.execute("""
    ALTER TABLE account_move 
    ADD COLUMN IF NOT EXISTS payment_journal_id INT,
    ADD COLUMN IF NOT EXISTS payment_mechanism_id INT,
    ADD COLUMN IF NOT EXISTS l10n_pt_at_sent BOOLEAN,
    ADD COLUMN IF NOT EXISTS pt_arxi_validated_date TIMESTAMP,
    ADD COLUMN IF NOT EXISTS hash_control VARCHAR(70)
    """)
    cr.execute(
        """
        UPDATE account_move
        SET payment_journal_id = ai.payment_journal_id,
            payment_mechanism_id = ai.payment_mechanism_id,
            l10n_pt_at_sent = ai.l10n_pt_at_sent,
            pt_arxi_inalterable_hash = ai.hash,
            pt_arxi_validated_date = ai.pt_arxi_validated_date,
            hash_control = ai.hash_control
        FROM account_invoice ai
        WHERE ai.move_id = account_move.id
        """
    )
    # Updating cancelled invoice name
    cr.execute(
        """
        UPDATE account_move am 
        SET name = ai.move_name 
        FROM account_invoice ai 
        WHERE ai.move_id = am.id 
        AND am.state = 'cancel' 
        AND am.move_type IN ('out_invoice', 'out_refund');
        """
    )

def migrate(cr, version):
    # Disable restrict_mode_hash_table for PT/AO bank and cash journals directly in SQL to bypass ORM constraints.
    cr.execute(
        """
        UPDATE account_journal aj
           SET restrict_mode_hash_table = FALSE
          FROM res_company rc
          JOIN res_country c ON c.id = rc.account_fiscal_country_id
         WHERE aj.company_id = rc.id
           AND c.code IN ('PT', 'AO')
           AND aj.type IN ('bank', 'cash')
           AND COALESCE(aj.restrict_mode_hash_table, FALSE) = TRUE
        """
    )

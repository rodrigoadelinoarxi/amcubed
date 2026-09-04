def migrate(cr, version):
    cr.execute("""ALTER TABLE sale_order ADD COLUMN IF NOT EXISTS pt_arxi_inalterable_hash VARCHAR""")
    cr.execute("""UPDATE sale_order SET pt_arxi_inalterable_hash = hash""")

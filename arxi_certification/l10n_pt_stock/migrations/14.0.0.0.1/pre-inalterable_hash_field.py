def migrate(cr, version):
    cr.execute("""ALTER TABLE stock_picking ADD COLUMN IF NOT EXISTS pt_arxi_inalterable_hash VARCHAR""")
    cr.execute("""UPDATE stock_picking SET pt_arxi_inalterable_hash = hash""")
    cr.execute("""ALTER TABLE pt_transport ADD COLUMN IF NOT EXISTS pt_arxi_inalterable_hash VARCHAR""")
    cr.execute("""UPDATE pt_transport SET pt_arxi_inalterable_hash = hash""")

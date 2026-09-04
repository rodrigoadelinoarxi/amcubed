
def migrate(cr, version):
    cr.execute(
        """ALTER TABLE account_report_expression DROP CONSTRAINT account_report_expression_line_label_uniq""")
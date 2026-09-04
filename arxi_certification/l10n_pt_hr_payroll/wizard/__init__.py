from . import export_dmr
from . import export_dri
from . import export_income_deduction_mixin
from . import export_income
from . import export_deductions
from . import export_insurance_map
from . import hr_payroll_account_sepa_wizard
# DESACTIVADO 2026-08-27: herdava hr.payslip.employees, wizard que a v19
# removeu. A geracao em lote passou para hr.payslip.run.generate_payslips().
# Os metodos-ancora que este wizard sobrepunha (compute_sheet, _filter_contracts)
# tambem desapareceram, por isso os recibos extraordinarios/bonus ficam
# indisponiveis ate a Arxi redesenhar o fluxo para a v19.
# from . import hr_payroll_payslips_by_employees
from . import hr_payroll_edit_payslip_lines_wizard

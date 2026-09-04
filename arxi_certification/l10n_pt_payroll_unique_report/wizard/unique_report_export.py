from odoo import models, fields, _
import os
import base64
import xmlschema
from xmlschema import XMLResource
import logging
from odoo.exceptions import ValidationError
_logger = logging.getLogger(__name__)


class UniqueReportExportWizard(models.TransientModel):
    _name = 'unique.report.export.wizard'
    _description = 'Unique Report Export Wizard'

    unique_report_id = fields.Many2one('unique.report', string="Unique Report", required=True)

    state = fields.Selection([
        ('get', 'get'),
        ('error', 'error'),
    ], readonly=True)

    xml_file = fields.Binary("File", readonly=True)
    xml_filename = fields.Char("Filename", readonly=True)
    result = fields.Text(readonly=True)

    def export_xml(self):
        self.ensure_one()

        annex = self.env.context.get('export_annex', 'annex_0')

        template_mapping = {
            'annex_0': {
                'template': 'l10n_pt_payroll_unique_report.unique_report_annex_0',
                'xsd'     : 'relatorio-zero-3.2.13.xsd',
                'filename': f'relatorio_unico_annex_0_{self.unique_report_id.reference_year}.xml',
            },
            'annex_a': {
                'template': 'l10n_pt_payroll_unique_report.unique_report_annex_a',
                'xsd'     : 'relatorio-qp-3.2.13.xsd',
                'filename': f'relatorio_unico_annex_a_{self.unique_report_id.reference_year}.xml',
            },
            'annex_b': {
                'template': 'l10n_pt_payroll_unique_report.unique_report_annex_b',
                'xsd'     : 'relatorio-fest-3.2.13.xsd',
                'filename': f'relatorio_unico_annex_b_{self.unique_report_id.reference_year}.xml',
            },
            'annex_c': {
                'template': 'l10n_pt_payroll_unique_report.unique_report_annex_c',
                'xsd'     : 'relatorio-rfc-3.2.13.xsd',
                'filename': f'relatorio_unico_annex_c_{self.unique_report_id.reference_year}.xml',
            },
            'annex_e': {
                'template': 'l10n_pt_payroll_unique_report.unique_report_annex_e',
                'xsd'     : 'relatorio-grv-3.2.13.xsd',
                'filename': f'relatorio_unico_annex_e_{self.unique_report_id.reference_year}.xml',
            }
        }

        config = template_mapping.get(annex)
        if not config:
            raise ValidationError(_("Unsupported annex: %s") % annex)

        try:
            # Render do template XML
            xml_rendered = self.env['ir.qweb']._render(
                config['template'],
                values={'o': self.unique_report_id}
            )
            xml_str = xml_rendered.decode('utf-8') if isinstance(xml_rendered, bytes) else xml_rendered

            # Caminho do XSD
            module_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
            xsd_path = os.path.join(module_path, 'data', config['xsd'])

            # Validação com o XSD
            schema = xmlschema.XMLSchema11(xsd_path)
            schema.validate(xml_str)

            # Escrever com estado de sucesso
            self.write({
                'state'       : 'get',
                'xml_file'    : base64.b64encode(xml_str.encode('utf-8')),
                'xml_filename': config['filename'],
                'result'      : False,
            })

        except xmlschema.XMLSchemaValidationError as e:
            # Mesmo com erro, permite o download do ficheiro com erro visível
            self.write({
                'state'       : 'error',
                'xml_file'    : base64.b64encode(xml_str.encode('utf-8')),
                'xml_filename': config['filename'],
                'result'      : e.message,
            })

        except Exception as e:
            raise ValidationError(_("Error generating XML: %s") % str(e))

        return {
            'type'     : 'ir.actions.act_window',
            'res_model': 'unique.report.export.wizard',
            'view_mode': 'form',
            'res_id'   : self.id,
            'target'   : 'new',
        }

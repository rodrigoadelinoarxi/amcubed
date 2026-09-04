import logging
from lxml import etree
from odoo import models, fields, _
from odoo.tools.xml_utils import create_xml_node, create_xml_node_chain

_logger = logging.getLogger(__name__)


class AccountJournal(models.Model):
    _inherit = "account.journal"

    # def _get_CtgyPurp(self):

    def _get_PmtTpInf(self, sct_generic=False, local_instrument=None):
        PmtTpInf = etree.Element("PmtTpInf")
        if self.env.context.get('payslip_sepa'):
            CtgyPurp = etree.SubElement(PmtTpInf, "CtgyPurp")
            Cd = etree.SubElement(CtgyPurp, "Cd")
            Cd.text = 'SALA'
        else:
            SvcLvl = etree.SubElement(PmtTpInf, "SvcLvl")
            Cd = etree.SubElement(SvcLvl, "Cd")
            Cd.text = 'SEPA'

        if local_instrument:
            create_xml_node_chain(PmtTpInf, ['LclInstrm', 'Prtry'], local_instrument)
        return PmtTpInf

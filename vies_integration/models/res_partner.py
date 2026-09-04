import logging
import re

from odoo import api, models
from stdnum.eu import vat as stdnum_vat
from stdnum.exceptions import InvalidChecksum, InvalidComponent, InvalidFormat, InvalidLength, ValidationError
from zeep import helpers

_logger = logging.getLogger(__name__)

_country_codes = {'AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI', 'FR', 'GB', 'GR', 'HR', 'HU', 'IE', 'IT',
                  'LT', 'LU', 'LV', 'MT', 'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK'}


class Partner(models.Model):
    _inherit = "res.partner"

    @api.onchange('vat', 'country_id')
    def onchange_vies_vat(self):
        """
        The VIES Webservice doesn't return a formatted address, making it impossible to know exactly from a
        string, which fields to update.
        """
        if self.vat and self.country_id and self.country_id.code in _country_codes:
            vat = self.country_id.code + self.vat if self.vat[:2].upper() != self.country_id.code else self.vat
            try:
                res = stdnum_vat.check_vies(vat)
                data = helpers.serialize_object(res, dict)  # cast to dict
                if not data.get('valid'):
                    _logger.info("Invalid VAT and Country code combination: %s" % vat)
                    return False

                address = data['address'].splitlines()
                vals = {}
                if data.get('name', '---') != '---':
                    vals.update({'name': data['name']})

                # This allows a creating a method for each country with its own specific rules
                # for address formatting
                format_func = getattr(self, 'vies_format_address_' + self.country_id.code.lower(), None)
                if not format_func:
                    vals.update({
                        'street': ' - '.join(address)
                    })
                else:
                    vals.update(format_func(address))
                self.update(vals)
            except (InvalidComponent, ValidationError, InvalidChecksum, InvalidFormat, InvalidLength):
                _logger.info('One of the parts of the number are invalid or unknown')
            except Exception:
                _logger.info("Invalid VAT and Country code combination: %s" % vat)
            else:
                _logger.info(data)

    @api.model
    def vies_format_address_pt(self, address):
        def vies_format_zip_code_pt(zip_code):
            res = re.search(r'\d{4}-\d{3}', zip_code)
            return res and res.group() or ''

        vals = {}
        if len(address) == 4:
            vals.update({
                'street' : address[0],
                'street2': address[1],
                'city'   : address[2],
                'zip'    : vies_format_zip_code_pt(address[3])
            })
        else:
            vals.update({
                'street': address[0] if len(address) >= 1 else "",
                'city'  : address[1] if len(address) >= 2 else "",
                'zip'   : vies_format_zip_code_pt(address[2]) if len(address) >= 3 else ""
            })
        return vals

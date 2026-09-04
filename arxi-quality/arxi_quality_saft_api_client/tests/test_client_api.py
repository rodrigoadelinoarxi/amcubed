from odoo.addons.base.tests.common import HttpCaseWithUserDemo

from odoo.addons.arxi_quality_saft_api_client.controllers.main import ArxiQualityApiClient as controller
from odoo.tests.common import TransactionCase, tagged
from datetime import datetime, timedelta

import logging
import json

_logger = logging.getLogger(__name__)


class TestQualityApiClient(HttpCaseWithUserDemo):

    def setUp(self):
        # response = self.url_open(url="https://girt-staging.odoo.com/export/saft", data=json.dumps(post_data), headers=headers)
        super(TestQualityApiClient, self).setUp()
        self.base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

    @tagged("at_install")
    def test_controller_token_validation_empty(self):
        a_simple_url = self.base_url + controller._webhook_url
        headers = {
            'Content-Type': 'application/json'
        }
        post_data = {
            "params": {
                "api_token": "",
                "saft_data": {
                    "date_start": "2024-09-01",
                    "date_end"  : "2024-09-02"
                }
            }
        }
        response = self.url_open(url=a_simple_url, data=json.dumps(post_data), headers=headers)
        result = response.json().get('result')
        self.assertEqual(result.get('status'), 401)
        self.assertEqual(result.get('response'), "Non-Authorized")

    @tagged("at_install")
    def test_controller_token_validation_wrong(self):
        a_simple_url = self.base_url + controller._webhook_url
        headers = {
            'Content-Type': 'application/json'
        }
        post_data = {
            "params": {
                "api_token": "invalid_q$Nr*FY3CzuhbpnFzZ8tyMWJ53D9DwiW#",
                "saft_data": {
                    "date_start": "2024-09-01",
                    "date_end"  : "2024-09-02"
                }
            }
        }
        response = self.url_open(url=a_simple_url, data=json.dumps(post_data), headers=headers)
        result = response.json().get('result')
        self.assertEqual(result.get('status'), 401)
        self.assertEqual(result.get('response'), "Non-Authorized")

    @tagged("at_install")
    def test_controller_token_validation_missing_fields(self):
        a_simple_url = self.base_url + controller._webhook_url
        headers = {
            'Content-Type': 'application/json'
        }
        post_data_missing_saft_data = {
            "params": {
                "api_token": "invalid_q$Nr*FY3CzuhbpnFzZ8tyMWJ53D9DwiW#",
            }
        }
        post_data_missing_date_start = {
            "params": {
                "api_token": "invalid_q$Nr*FY3CzuhbpnFzZ8tyMWJ53D9DwiW#",
                "saft_data": {
                    "date_end": "2024-09-02"
                }
            }
        }
        post_data_missing_date_end = {
            "params": {
                "api_token": "invalid_q$Nr*FY3CzuhbpnFzZ8tyMWJ53D9DwiW#",
                "saft_data": {
                    "date_start": "2024-09-01",
                }
            }
        }
        response_missing_saft_data = self.url_open(url=a_simple_url, data=json.dumps(post_data_missing_saft_data),
                                                   headers=headers)
        result_missing_saft_data = response_missing_saft_data.json().get('result')
        self.assertEqual(result_missing_saft_data.get('status'), 401)
        self.assertEqual(result_missing_saft_data.get('response'), "Non-Authorized")

        response_missing_date_start = self.url_open(url=a_simple_url, data=json.dumps(post_data_missing_date_start),
                                                    headers=headers)
        result_missing_date_start = response_missing_date_start.json().get('result')
        self.assertEqual(result_missing_date_start.get('status'), 401)
        self.assertEqual(result_missing_date_start.get('response'), "Non-Authorized")

        response_missing_date_end = self.url_open(url=a_simple_url, data=json.dumps(post_data_missing_date_end),
                                                  headers=headers)
        result_missing_date_end = response_missing_date_end.json().get('result')
        self.assertEqual(result_missing_date_end.get('status'), 401)
        self.assertEqual(result_missing_date_end.get('response'), "Non-Authorized")

    @tagged("at_install")
    def test_controller_response_structure(self):
        a_simple_url = self.base_url + controller._webhook_url
        date_start = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        date_end = datetime.now().strftime('%Y-%m-%d')
        internal_api_key = self.env['ir.config_parameter'].sudo().get_param('arxi_saft_api_token')
        headers = {
            'Content-Type': 'application/json'
        }
        post_data = {
            "params": {
                "api_token": internal_api_key,
                "saft_data": {
                    "date_start": date_start,
                    "date_end"  : date_end
                }
            }
        }
        response = self.url_open(url=a_simple_url, data=json.dumps(post_data), headers=headers)
        result = response.json().get('result')
        status = result.get('status')
        self.assertIn('status', result)
        self.assertIn('response', result)
        if status == 200:
            self.assertIn('record_amount_total', result)
            self.assertIn('xml', result)
            self.assertIn('encoded_doc', result)

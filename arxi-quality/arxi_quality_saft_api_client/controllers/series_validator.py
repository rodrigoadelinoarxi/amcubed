# -*- coding: utf-8 -*-
import csv
import json
import logging
from datetime import datetime
from pathlib import Path

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SeriesValidator(http.Controller):
    """
    Controller for validating and managing ATCUD series.
    Provides endpoints to check series compliance and auto-create missing series.
    """

    @http.route('/validate/series', type='json', auth='none', methods=['POST'], csrf=False)
    def validate_series(self, **post):
        """
        Single webhook endpoint with action-based routing for series management.
        Processes ALL eligible Portuguese companies (same logic as SAFT export).

        Expected payload:
        {
            "params": {
                "action": "check" | "create" | "edit" | "unlink",
                "db": "database_name",
                "year": 2025,
                ... other action-specific params
            }
        }
        """
        # Odoo JSON-RPC automatically unpacks 'params', so access directly from post
        action = post.get('action')

        # Authenticate database
        db = post.get('db')
        if db:
            try:
                request.session.db = db
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Database authentication failed: {str(e)}"
                }

        # Get eligible Portuguese companies (replicate SAFT logic from main.py)
        arr = []

        # Get ALL PT companies first
        pt_domain = [("account_fiscal_country_id.code", "=", "PT")]
        pt_company_ids = (
            request.env["res.company"].sudo().search(pt_domain, order="id asc")
        )

        # Get CERTIFIED PT companies (stricter domain)
        domain = [
            ("account_fiscal_country_id.code", "=", "PT"),
            ("company_registry", "!=", False),
            ("commercial_registry", "!=", False),
            ("l10n_pt_at_webservice", "=", True),
            ("parent_id", "=", False),
        ]
        cert_company_ids = (
            request.env["res.company"].sudo().search(domain, order="id asc")
        )

        # Check if no certified companies found
        if not cert_company_ids:
            return [
                {
                    "status": "error",
                    "response": "No company_ids matched the search.",
                    "error": "No certified Portuguese companies found with l10n_pt_at_webservice=True",
                    "company_id": 0,
                    "company_name": "None",
                }
            ]

        pt_company_ids = pt_company_ids - cert_company_ids
        # TODO: Maybe warn the user that there are PT companies that were not flagged as certified

        # Route to appropriate method for each company
        if action == 'check':
            year = post.get('year')
            if not year:
                return [
                    {
                        "status": "error",
                        "response": "Missing required parameter: year",
                        "error": "Year must be provided for series validation",
                    }
                ]

            _logger.info(f"[CHECK] Processing {len(cert_company_ids)} companies for year {year}")
            for company_id in cert_company_ids:
                company_result = self._check_series_for_company(year, company_id)
                arr.append(company_result)
            _logger.info(f"[CHECK] Completed processing {len(cert_company_ids)} companies for year {year}")
            return arr

        elif action == 'create':
            year = post.get('year')
            if not year:
                return [
                    {
                        "status": "error",
                        "response": "Missing required parameter: year",
                        "error": "Year must be provided for series creation",
                    }
                ]

            document_types = post.get('document_types')
            activate = post.get('activate', False)  # Default to False (draft)
            _logger.info(f"[CREATE] Processing {len(cert_company_ids)} companies for year {year} (activate={activate})")
            for company_id in cert_company_ids:
                company_result = self._create_series_for_company(year, company_id, document_types, activate)
                arr.append(company_result)
            _logger.info(f"[CREATE] Completed processing {len(cert_company_ids)} companies for year {year}")
            return arr

        elif action == 'edit':
            return self.edit_series(
                series_id=post.get('series_id'),
                updates=post.get('updates')
            )
        elif action == 'unlink':
            return self.unlink_series(
                series_id=post.get('series_id')
            )
        else:
            return [
                {
                    "status": "error",
                    "message": f"Unknown action: {action}. Valid actions: check, create, edit, unlink"
                }
            ]

    def _check_series_for_company(self, year, company):
        """
        Validates existing ATCUD series for a single company.

        :param year: Year to validate series for (e.g., 2025)
        :param company: Company record to validate
        :return: Dict with validation results categorized as: intact, bad, missing
        """
        _logger.info(f"[CHECK] Starting series validation for company '{company.name}' (ID: {company.id}) - Year: {year}")
        try:

            # Load CSV templates
            templates = self._load_series_templates()
            if not templates:
                return {
                    "status": "error",
                    "company": company.name,
                    "company_id": company.id,
                    "message": "Failed to load series templates from CSV"
                }

            # Filter templates based on installed modules, company configuration, and actual usage
            templates = self._filter_templates_by_modules(templates, company, year, action='check')
            if not templates:
                return {
                    "status": "success",
                    "year": year,
                    "company": company.name,
                    "company_id": company.id,
                    "message": "No applicable templates - required modules not installed or company features not enabled",
                    "summary": {
                        "total": 0,
                        "intact": 0,
                        "bad": 0,
                        "missing": 0
                    },
                    "results": {
                        "intact": [],
                        "bad": [],
                        "missing": []
                    }
                }

            # Query existing series for the year (both active and draft)
            series_model = request.env["l10n_pt.account.series"].sudo()
            try:
                existing_series = series_model.search([
                    ("company_id", "=", company.id),
                    ("initial_date", ">=", f"{year}-01-01"),
                    ("initial_date", "<=", f"{year}-12-31"),
                    ("state", "in", ["active", "draft"])
                ])
            except Exception as e:
                _logger.exception(f"Failed to query series for company {company.name}: {str(e)}")
                existing_series = series_model.browse([])

            # Initialize result categories
            intact_series = []
            bad_series = []
            missing_series = []

            # Check existing series - simple validation
            for series in existing_series:
                series_info = {
                    "code": series.code,
                    "document_type": series.document_type_id.name if series.document_type_id else "Unknown",
                    "document_type_code": series.document_type_id.code if series.document_type_id else "N/A",
                    "state": series.state,
                }

                # Simple validation: series is intact if it has a document_type_id
                # (year in code and state='active' already filtered in query)
                if not series.document_type_id:
                    series_info['issues'] = ["Missing document type"]
                    bad_series.append(series_info)
                else:
                    intact_series.append(series_info)

            # Check for missing series from templates - simplified to check by document type only
            # Get unique document types from templates
            doc_types_from_templates = {}
            for template in templates:
                doc_code = template['document_type_code']
                if doc_code not in doc_types_from_templates:
                    doc_types_from_templates[doc_code] = template

            # Check which document types have no active series with the year
            existing_doc_types = {s.document_type_id.code for s in existing_series if s.document_type_id}

            # Split missing series into two categories: with usage vs without usage
            missing_series_with_usage = []
            missing_series_no_usage = []

            for doc_code, template in doc_types_from_templates.items():
                # Check if any series exists for this document type
                if doc_code not in existing_doc_types:
                    # Count documents and get list of last 10 for this type in the year being validated
                    document_count, documents_list = self._count_documents_by_type(company, year, doc_code)

                    series_info = {
                        "pattern": template['series_pattern'],
                        "expected_code": template['series_pattern'].replace('{year}', str(year)),
                        "document_type": template['document_type_name'],
                        "document_type_code": template['document_type_code'],
                        "series_type": template['series_type'],
                        "processing_mode": template['processing_mode'],
                        "priority": template['priority'],
                        "document_count": document_count,
                        "documents": documents_list  # Include list of last 10 documents
                    }

                    # Split based on whether documents exist
                    if document_count > 0:
                        missing_series_with_usage.append(series_info)
                    else:
                        missing_series_no_usage.append(series_info)

            # Sort both lists by priority
            missing_series_with_usage.sort(key=lambda x: x['priority'])
            missing_series_no_usage.sort(key=lambda x: x['priority'])

            # Combine for total count (backward compatibility)
            all_missing = missing_series_with_usage + missing_series_no_usage

            # Build warnings array - only include missing series WITH document usage
            warnings = []
            if missing_series_with_usage:
                warnings.append({
                    "type": "missing_series",
                    "message": f"Found {len(missing_series_with_usage)} missing series with active documents for year {year}",
                    "details": missing_series_with_usage
                })

            _logger.info(
                f"[CHECK] Completed series validation for company '{company.name}' (ID: {company.id}) - "
                f"Intact: {len(intact_series)}, Bad: {len(bad_series)}, "
                f"Missing (with docs): {len(missing_series_with_usage)}, Missing (no docs): {len(missing_series_no_usage)}"
            )
            return {
                "status": "success",
                "year": year,
                "company": company.name,
                "company_id": company.id,
                "summary": {
                    "total": len(intact_series) + len(bad_series) + len(all_missing),
                    "intact": len(intact_series),
                    "bad": len(bad_series),
                    "missing": len(missing_series_with_usage),
                    "missing_no_usage": len(missing_series_no_usage)
                },
                "results": {
                    "intact": intact_series,
                    "bad": bad_series,
                    "missing": missing_series_with_usage,
                    "missing_no_usage": missing_series_no_usage
                },
                "warnings": warnings
            }

        except Exception as e:
            _logger.exception(f"[CHECK] Error checking series for company '{company.name}' (ID: {company.id}): {str(e)}")
            return {
                "status": "error",
                "company": company.name,
                "company_id": company.id,
                "message": f"Failed to check series: {str(e)}"
            }

    def _create_from_template(self, year, company, series_template, activate=False, activation_count=0, activation_limit=0):
        """
        Create a series based on template definition.
        Used for NEW document types (FS) not in previous year.

        :param year: Year to create series for
        :param company: Company record
        :param series_template: Dict from missing series (has pattern, doc_type, etc.)
        :param activate: If True, register with AT webservice (subject to activation limit)
        :param activation_count: Current number of activated series
        :param activation_limit: Maximum number of series to activate (default: 5)
        :return: Tuple (success: bool, series_info: dict, new_activation_count: int)
        """
        try:
            series_code = series_template['expected_code']
            doc_type_code = series_template['document_type_code']

            _logger.info(f"[TEMPLATE] Creating NEW series '{series_code}' ({doc_type_code}) from template")

            # Find document type record
            doc_type = request.env['account.document.type'].sudo().search([
                ('code', '=', doc_type_code)
            ], limit=1)

            if not doc_type:
                _logger.warning(f"[TEMPLATE] Document type {doc_type_code} not found in system")
                return False, {
                    "code": series_code,
                    "document_type_code": doc_type_code,
                    "reason": f"Document type {doc_type_code} not found in system"
                }

            # Create series with appropriate initial date
            # If we're before the target year, use January 1st of target year; otherwise use today
            today = datetime.today()
            initial_date = datetime(year, 1, 1).date() if today.year < year else today.date()

            series_vals = {
                'company_id': company.id,
                'name': f"{company.name} - {series_template['document_type']} - {series_code}",
                'code': series_code,
                'document_type_id': doc_type.id,
                'series_type': series_template.get('series_type', 'N'),
                'processing_mode': series_template.get('processing_mode', 'PI'),
                'initial_date': initial_date,
                'initial_number': 1,
            }

            # Add version-specific fields if they exist
            if hasattr(request.env['l10n_pt.account.series'], 'in_name_of'):
                series_vals['in_name_of'] = series_template.get('in_name_of', 'FN')

            new_series = request.env['l10n_pt.account.series'].sudo().create(series_vals)

            _logger.info(f"[TEMPLATE] Successfully created series '{new_series.code}' ({doc_type_code}) as {new_series.state}")

            # Activate series with AT if requested and under limit
            at_response = "Created as draft"
            validation_code = "N/A (draft)"
            series_code = new_series.code

            if activate and activation_count < activation_limit:
                try:
                    _logger.info(f"[TEMPLATE] Activating series '{series_code}' with AT webservice (count: {activation_count + 1}/{activation_limit})")
                    new_series.with_context(company_id=company.id).action_activate_non_blocking()
                    at_response = f"Activated with AT (state={new_series.state})"
                    validation_code = new_series.validation_code or "N/A"
                    activation_count += 1
                    _logger.info(f"[TEMPLATE] Series '{series_code}' activated successfully - validation_code: {validation_code}")
                except Exception as e:
                    _logger.exception(f"[TEMPLATE] Failed to activate series '{series_code}' with AT: {str(e)}")
                    at_response = f"Created but activation failed: {str(e)}"
            elif activate and activation_count >= activation_limit:
                _logger.info(f"[TEMPLATE] Activation limit reached ({activation_limit}) - keeping series '{series_code}' as draft")
                at_response = "Created as draft (activation limit reached)"

            return True, {
                "code": new_series.code,
                "document_type": series_template['document_type'],
                "document_type_code": doc_type_code,
                "validation_code": validation_code,
                "state": new_series.state,
                "at_response": at_response
            }, activation_count

        except Exception as e:
            _logger.exception(f"[TEMPLATE] Failed to create series '{series_code}' ({doc_type_code}) from template")
            return False, {
                "code": series_template.get('expected_code', 'Unknown'),
                "document_type_code": doc_type_code,
                "reason": f"Exception: {str(e)}"
            }, activation_count

    def _copy_previous_year_series(self, year, company, document_types=None, activate=False, activation_count=0, activation_limit=0):
        """
        Copy ALL series from previous year.

        :param year: Year to create series for
        :param company: Company record
        :param document_types: Optional list of document type codes to filter
        :param activate: If True, register with AT webservice (subject to activation limit)
        :param activation_count: Current number of activated series
        :param activation_limit: Maximum number of series to activate (default: 5)
        :return: Dict with results {
            'created': [...],
            'failed': [...],
            'already_exists': [...],
            'prev_year_doc_types': set(),  # Document type codes that existed in prev year
            'activation_count': int  # Updated activation count
        }
        """
        series_model = request.env["l10n_pt.account.series"].sudo()
        prev_year = year - 1

        # Query previous year active series
        prev_series = series_model.search([
            ("company_id", "=", company.id),
            ("initial_date", ">=", f"{prev_year}-01-01"),
            ("initial_date", "<=", f"{prev_year}-12-31"),
            ("state", "=", "active"),
            ("document_type_id", "!=", False)
        ])

        # Track which document types existed in previous year
        prev_year_doc_types = {s.document_type_id.code for s in prev_series if s.document_type_id}

        # If no previous year series found, return empty results
        if not prev_series:
            return {
                'created': [],
                'failed': [],
                'already_exists': [],
                'prev_year_doc_types': set(),
                'activation_count': activation_count
            }

        # Filter by document types if specified
        if document_types:
            prev_series = prev_series.filtered(
                lambda s: s.document_type_id.code in document_types
            )

        # Query existing series for current year (both active and draft to avoid duplicates)
        existing_series = series_model.search([
            ("company_id", "=", company.id),
            ("initial_date", ">=", f"{year}-01-01"),
            ("initial_date", "<=", f"{year}-12-31"),
            ("state", "in", ["active", "draft"])
        ])
        existing_series_keys = {(s.code, s.document_type_id.id) for s in existing_series}

        # Initialize result categories
        created_series = []
        failed_series = []
        already_exists = []

        _logger.info(f"[COPY] Found {len(prev_series)} series from year {prev_year} to copy to year {year} for company {company.name}")

        # Copy each series from previous year
        for prev in prev_series:
            try:
                # Generate new code by replacing year
                old_code = prev.code

                if str(prev_year) in old_code:
                    new_code = old_code.replace(str(prev_year), str(year))
                else:
                    new_code = old_code + str(year)

                # Check if series already exists
                if (new_code, prev.document_type_id.id) in existing_series_keys:
                    _logger.info(f"[COPY] Series '{new_code}' ({prev.document_type_id.code}) already exists - skipping")
                    already_exists.append({
                        "code": new_code,
                        "copied_from": old_code,
                        "document_type": prev.document_type_id.name,
                        "document_type_code": prev.document_type_id.code,
                        "reason": "Series already exists for this year"
                    })
                    continue

                _logger.info(f"[COPY] Creating series '{new_code}' ({prev.document_type_id.code}) from '{old_code}'")

                # Create new series with appropriate initial date
                # If we're before the target year, use January 1st of target year; otherwise use today
                today = datetime.today()
                initial_date = datetime(year, 1, 1).date() if today.year < year else today.date()

                series_vals = {
                    'company_id': company.id,
                    'name': f"{company.name} - {prev.document_type_id.name} - {new_code}",
                    'code': new_code,
                    'document_type_id': prev.document_type_id.id,
                    'series_type': prev.series_type,
                    'processing_mode': prev.processing_mode,
                    'initial_date': initial_date,
                    'initial_number': 1,
                }

                if hasattr(prev, 'in_name_of'):
                    series_vals['in_name_of'] = prev.in_name_of or 'FN'

                new_series = series_model.create(series_vals)

                _logger.info(f"[COPY] Successfully created series '{new_series.code}' ({prev.document_type_id.code}) as {new_series.state}")

                # Activate series with AT if requested and under limit
                at_response = "Created as draft"
                validation_code = "N/A (draft)"
                series_code = new_series.code

                if activate and activation_count < activation_limit:
                    try:
                        _logger.info(f"[COPY] Activating series '{series_code}' with AT webservice (count: {activation_count + 1}/{activation_limit})")
                        new_series.with_context(company_id=company.id).action_activate_non_blocking()
                        at_response = f"Activated with AT (state={new_series.state})"
                        validation_code = new_series.validation_code or "N/A"
                        activation_count += 1
                        _logger.info(f"[COPY] Series '{series_code}' activated successfully - validation_code: {validation_code}")
                    except Exception as e:
                        _logger.exception(f"[COPY] Failed to activate series '{series_code}' with AT: {str(e)}")
                        at_response = f"Created but activation failed: {str(e)}"
                elif activate and activation_count >= activation_limit:
                    _logger.info(f"[COPY] Activation limit reached ({activation_limit}) - keeping series '{series_code}' as draft")
                    at_response = "Created as draft (activation limit reached)"

                created_series.append({
                    "code": new_series.code,
                    "document_type": prev.document_type_id.name,
                    "document_type_code": prev.document_type_id.code,
                    "validation_code": validation_code,
                    "state": new_series.state,
                    "copied_from": old_code,
                    "at_response": at_response
                })

            except Exception as e:
                error_str = str(e).lower()
                if 'duplicate key' in error_str or 'already exists' in error_str or 'unique constraint' in error_str:
                    _logger.warning(f"[COPY] Duplicate series detected: '{new_code}' ({prev.document_type_id.code})")
                    already_exists.append({
                        "code": new_code if 'new_code' in locals() else 'Unknown',
                        "copied_from": prev.code,
                        "document_type": prev.document_type_id.name,
                        "document_type_code": prev.document_type_id.code,
                        "reason": "Series already exists in database"
                    })
                else:
                    _logger.exception(f"[COPY] Failed to create series '{new_code}' ({prev.document_type_id.code}) from '{old_code}'")
                    failed_series.append({
                        "code": new_code if 'new_code' in locals() else 'Unknown',
                        "copied_from": prev.code,
                        "document_type": prev.document_type_id.name,
                        "document_type_code": prev.document_type_id.code,
                        "reason": f"Exception: {str(e)}"
                    })

        return {
            'created': created_series,
            'failed': failed_series,
            'already_exists': already_exists,
            'prev_year_doc_types': prev_year_doc_types,
            'activation_count': activation_count
        }

    def _create_series_for_company(self, year, company, document_types=None, activate=False):
        """
        Auto-creates ATCUD series for a single company using check-first logic.

        Flow:
        1. Check current state (which series exist/missing)
        2. Copy ALL series from previous year
        3. Auto-create NEW template types (FS) if documents exist
        4. Check final state and return check-style response

        :param year: Year to create series for (e.g., 2026)
        :param company: Company record
        :param document_types: Optional list of document type codes to create (None = create all)
        :param activate: If True, register series with AT webservice and set state='active'. If False, leave as draft.
        :return: Dict with check-style response (intact, bad, missing arrays) + creation_summary
        """
        _logger.info(f"[CREATE] Starting series creation for company '{company.name}' (ID: {company.id}) - Year: {year}")
        try:
            # Check if AT webservice is configured (only required if activate=True)
            if activate and not company.l10n_pt_at_webservice:
                return {
                    "status": "error",
                    "company": company.name,
                    "company_id": company.id,
                    "message": "AT webservice not enabled for company - cannot activate series"
                }

            # STEP 1: Check current state BEFORE creation
            pre_check = self._check_series_for_company(year, company)
            if pre_check.get('status') == 'error':
                return pre_check

            # STEP 1.5: Block creation if no previous year series exist
            prev_year = year - 1
            series_model = request.env["l10n_pt.account.series"].sudo()
            has_prev_year_series = series_model.search_count([
                ("company_id", "=", company.id),
                ("initial_date", ">=", f"{prev_year}-01-01"),
                ("initial_date", "<=", f"{prev_year}-12-31"),
                ("state", "=", "active"),
                ("document_type_id", "!=", False)
            ]) > 0

            if not has_prev_year_series:
                _logger.warning(f"[CREATE] Blocking auto-creation for {company.name} year {year} - no active series found in {prev_year}")
                return {
                    "status": "error",
                    "company": company.name,
                    "company_id": company.id,
                    "year": year,
                    "message": f"Cannot auto-create series - no series found for previous year ({prev_year}). Please create {prev_year} or {year} series manually first. Contact your Project Manager for assistance."
                }

            # STEP 2: Copy ALL series from previous year (with activation limit of 5)
            activation_count = 0  # Track total activations across all operations
            activation_limit = 99  # Maximum number of series to activate

            copy_results = self._copy_previous_year_series(year, company, document_types, activate, activation_count, activation_limit)
            prev_year_doc_types = copy_results['prev_year_doc_types']
            activation_count = copy_results['activation_count']  # Update count from copy operation

            # STEP 3: Auto-create from templates
            created_from_templates = []
            failed_from_templates = []

            # Determine which missing series to create
            if not prev_year_doc_types:
                # NO previous year series - create ALL templates regardless of document usage
                _logger.info(f"[CREATE] No previous year series found - creating ALL {len(pre_check['results'].get('missing', []) + pre_check['results'].get('missing_no_usage', []))} series from templates")
                missing_to_create = pre_check['results'].get('missing', []) + pre_check['results'].get('missing_no_usage', [])
            else:
                # Previous year series exist - only create NEW types that have documents
                _logger.info(f"[CREATE] Previous year series found ({len(prev_year_doc_types)} types) - creating only {len(pre_check['results'].get('missing', []))} NEW types with documents")
                missing_to_create = pre_check['results'].get('missing', [])

            _logger.info(f"[CREATE] Processing {len(missing_to_create)} missing series for template creation")
            for missing_series in missing_to_create:
                doc_type_code = missing_series['document_type_code']

                # Only create from template if it didn't exist in previous year (NEW type like FS)
                if doc_type_code not in prev_year_doc_types:
                    doc_count = missing_series.get('document_count', 0)
                    _logger.info(f"[CREATE] Attempting template creation for {doc_type_code} ({doc_count} documents)")
                    success, series_info, activation_count = self._create_from_template(
                        year, company, missing_series, activate, activation_count, activation_limit
                    )

                    if success:
                        created_from_templates.append(series_info)
                    else:
                        failed_from_templates.append(series_info)
                else:
                    _logger.info(f"[CREATE] Skipping {doc_type_code} - already existed in previous year (should have been copied)")

            # STEP 4: Check final state AFTER all creation
            post_check = self._check_series_for_company(year, company)
            if post_check.get('status') == 'error':
                # If post-check fails, return partial success with what we know
                return {
                    "status": "partial_success",
                    "year": year,
                    "company": company.name,
                    "company_id": company.id,
                    "message": "Series created but final validation failed",
                    "creation_summary": {
                        "copied_from_prev_year": len(copy_results['created']),
                        "created_from_templates": len(created_from_templates),
                        "failed": len(copy_results['failed']) + len(failed_from_templates),
                        "already_exists": len(copy_results['already_exists'])
                    }
                }

            # STEP 5: Return check-style response with creation summary
            _logger.info(
                f"[CREATE] Completed series creation for company '{company.name}' (ID: {company.id}) - "
                f"Created: {len(copy_results['created']) + len(created_from_templates)}, "
                f"Failed: {len(copy_results['failed']) + len(failed_from_templates)}, "
                f"Already exists: {len(copy_results['already_exists'])}"
            )
            return {
                "status": "success",
                "year": year,
                "company": company.name,
                "company_id": company.id,
                "summary": post_check['summary'],  # intact, bad, missing, missing_no_usage counts
                "results": post_check['results'],  # intact[], bad[], missing[], missing_no_usage[] arrays
                "creation_summary": {
                    "copied_from_prev_year": len(copy_results['created']),
                    "created_from_templates": len(created_from_templates),
                    "failed": len(copy_results['failed']) + len(failed_from_templates),
                    "already_exists": len(copy_results['already_exists']),
                    "prev_year_doc_types": list(prev_year_doc_types)  # For debugging
                },
                "creation_details": {
                    "copied": copy_results['created'],
                    "created_from_templates": created_from_templates,
                    "failed": copy_results['failed'] + failed_from_templates,
                    "already_exists": copy_results['already_exists']
                },
                "warnings": post_check.get('warnings', [])
            }

        except Exception as e:
            _logger.exception(f"[CREATE] Error creating series for company '{company.name}' (ID: {company.id}): {str(e)}")
            return {
                "status": "error",
                "company": company.name,
                "company_id": company.id,
                "message": f"Failed to create series: {str(e)}"
            }

    def edit_series(self, series_id, updates):
        """
        Edit an existing ATCUD series.
        TODO: Implement series editing functionality.

        :param series_id: ID of series to edit
        :param updates: Dict of fields to update
        :return: Dict with edit result
        """
        return {
            "status": "not_implemented",
            "message": "Edit functionality coming soon"
        }

    def unlink_series(self, series_id):
        """
        Delete an ATCUD series.
        TODO: Implement series deletion functionality.

        :param series_id: ID of series to delete
        :return: Dict with deletion result
        """
        return {
            "status": "not_implemented",
            "message": "Unlink functionality coming soon"
        }

    # Helper methods

    def _load_series_templates(self):
        """
        Load series templates from CSV file.

        :return: List of template dicts
        """
        try:
            csv_path = Path(__file__).parent.parent / 'data' / 'series_templates.csv'

            if not csv_path.exists():
                _logger.error(f"Series templates CSV not found at: {csv_path}")
                return []

            templates = []
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    templates.append({
                        'document_type_code': row['document_type_code'],
                        'document_type_name': row['document_type_name'],
                        'series_pattern': row['series_pattern'],
                        'series_type': row['series_type'],
                        'processing_mode': row['processing_mode'],
                        'in_name_of': row['in_name_of'],
                        'category': row['category'],
                        'priority': int(row['priority'])
                    })

            return templates

        except Exception as e:
            _logger.exception("Failed to load series templates from CSV")
            return []

    def _match_series_to_template(self, series, templates, year):
        """
        Check if a series matches any template pattern.

        :param series: Series recordset (single record)
        :param templates: List of template dicts
        :param year: Year to check
        :return: Matched template dict or None
        """
        series_code = series.code
        doc_type_code = series.document_type_id.code if series.document_type_id else None

        if not doc_type_code:
            return None

        for template in templates:
            # Check if document type matches
            if template['document_type_code'] != doc_type_code:
                continue

            # Check if series code matches pattern
            expected_code = template['series_pattern'].replace('{year}', str(year))
            if series_code == expected_code:
                return template

        return None

    def _validate_with_at(self, company, series_recordset):
        """
        Validate series with AT webservice.

        :param company: Company record
        :param series_recordset: Recordset of series to validate
        :return: Dict mapping series_code to validation results
        """
        results = {}

        try:
            if not company.l10n_pt_at_api_username or not company.l10n_pt_at_api_password:
                return results

            # Use first series to access AT webservice methods
            if not series_recordset:
                return results

            first_series = series_recordset[0]

            # Query AT for series list
            # at_ws_series_read() returns (code, msg, infoSerie_data)
            code, msg, series_list = first_series.with_context(company_id=company.id).at_ws_series_read()

            if code not in [2000, 2001, 2002]:
                _logger.warning(f"Failed to query AT for series list: {msg}")
                return results

            # Ensure series_list is a list
            if not series_list:
                series_list = []
            elif isinstance(series_list, dict):
                series_list = [series_list]

            # Create lookup dict
            at_series_dict = {
                f"{s['serie']}_{s['tipoDoc']}": s
                for s in series_list
            }

            # Validate each series
            for series in series_recordset:
                series_key = f"{series.code}_{series.document_type_id.code}"
                at_series = at_series_dict.get(series_key)

                issues = []

                if not at_series:
                    issues.append("Series not found in AT registry")
                else:
                    # Check validation code
                    if series.validation_code and at_series.get('codValidacaoSerie') != series.validation_code:
                        issues.append(
                            f"Validation code mismatch - Odoo: {series.validation_code}, "
                            f"AT: {at_series.get('codValidacaoSerie')}"
                        )

                    # Check state
                    at_state_map = {'A': 'active', 'C': 'cancelled', 'D': 'done'}
                    at_state = at_state_map.get(at_series.get('estado'), 'unknown')

                    if at_state != series.state:
                        issues.append(
                            f"State mismatch - Odoo: {series.state}, AT: {at_state}"
                        )

                results[series.code] = {
                    'issues': issues,
                    'at_found': at_series is not None
                }

        except Exception as e:
            _logger.exception("Failed to validate with AT webservice")

        return results

    def _is_module_installed(self, module_name):
        """
        Check if a module is installed in the current database.

        :param module_name: Name of the module to check
        :return: Boolean indicating if module is installed
        """
        try:
            is_installed = (
                request.env["ir.module.module"]
                .sudo()
                .search([("name", "=", module_name), ("state", "=", "installed")])
            )
            return bool(is_installed)
        except Exception as e:
            _logger.warning(f"Failed to check if module {module_name} is installed: {str(e)}")
            return False  # Explicitly return False on error

    def _company_uses_proforma(self, company, year):
        """
        Check if company has proforma invoices (PF) in the given year.

        :param company: Company record
        :param year: Year to check (e.g., 2025)
        :return: Boolean indicating if company uses proformas in that year
        """
        try:
            # Check if l10n_pt_sale module is installed (provides sale_type_id field)
            if not self._is_module_installed('l10n_pt_sale'):
                _logger.info("l10n_pt_sale module not installed - skipping PF validation")
                return False

            # Query sale.order for proforma invoices in the given year
            year_start = datetime(year, 1, 1)
            year_end = datetime(year, 12, 31, 23, 59, 59)

            # Check if sale_type_id field exists (v18+)
            if 'sale_type_id' in request.env["sale.order"]._fields:
                proforma_count = (
                    request.env["sale.order"]
                    .sudo()
                    .search_count([
                        ("company_id", "=", company.id),
                        ("date_order", ">=", year_start),
                        ("date_order", "<=", year_end),
                        ("sale_type_id.code", "=", "PF")
                    ])
                )
                return proforma_count > 0
            else:
                # v17 or instances without sale_type_id: assume no proformas
                _logger.info("sale_type_id field not found - skipping PF validation (v17 compatibility)")
                return False
        except Exception as e:
            _logger.warning(f"Failed to check if company uses proforma: {str(e)}")
            # On error, assume they don't use it (safer for v17)
            return False

    def _count_documents_by_type(self, company, year, doc_type_code):
        """
        Count documents of a specific type for the given company and year.
        Returns both count and list of last 10 documents.

        :param company: Company record
        :param year: Year to check
        :param doc_type_code: Document type code (RG, FT, NC, PF, OR, GT)
        :return: Tuple (count, list_of_last_10_documents)
        """
        count_methods = {
            'RG': self._count_rg_documents,
            'FT': self._count_ft_documents,
            'FS': self._count_fs_documents,
            'NC': self._count_nc_documents,
            'PF': self._count_pf_documents,
            'OR': self._count_or_documents,
        }

        count_method = count_methods.get(doc_type_code)
        if count_method:
            return count_method(company, year)

        _logger.warning(f"No count method for document type: {doc_type_code}")
        return 0, []

    def _count_rg_documents(self, company, year):
        """
        Count RG (Recibo/Payment) documents using SAFT export filters.
        Returns count and list of last 10 documents.

        :param company: Company record
        :param year: Year to check
        :return: Tuple (count, list_of_documents)
        """
        try:
            year_start = datetime(year, 1, 1).date()
            year_end = datetime(year, 12, 31).date()

            domain = [
                ("journal_id.l10n_cert", "=", True),
                ("validated_date", "!=", False),
                ("posting_date", ">=", year_start),
                ("posting_date", "<=", year_end),
                ("payment_type", "=", "inbound"),
                ("partner_type", "=", "customer"),
                ("is_selfpaid", "=", False),
                ("company_id", "=", company.id),
                "|",
                ("move_id.status_id.code", "=", "N"),
                ("move_id.status_id.code", "=", "A"),
            ]

            # Get count
            payment_count = request.env["account.payment"].sudo().search_count(domain)

            # Get last 10 documents
            documents_list = []
            if payment_count > 0:
                payments = (
                    request.env["account.payment"]
                    .sudo()
                    .search(domain, order="posting_date desc", limit=10)
                )
                for payment in payments:
                    documents_list.append({
                        "name": payment.payment_name or payment.name,
                        "date": str(payment.posting_date),
                        "partner": payment.partner_id.name if payment.partner_id else "N/A",
                        "amount": payment.amount,
                    })

            return payment_count, documents_list
        except Exception as e:
            _logger.warning(f"Failed to count RG documents: {str(e)}")
            return 0, []

    def _count_ft_documents(self, company, year):
        """
        Count FT (Fatura/Invoice) documents.
        Returns count and list of last 10 documents.

        :param company: Company record
        :param year: Year to check
        :return: Tuple (count, list_of_documents)
        """
        try:
            year_start = datetime(year, 1, 1).date()
            year_end = datetime(year, 12, 31).date()

            domain = [
                ("move_type", "=", "out_invoice"),
                ("document_type_id.code", "=", "FT"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", year_start),
                ("invoice_date", "<=", year_end),
                ("company_id", "=", company.id),
            ]

            # Get count
            invoice_count = request.env["account.move"].sudo().search_count(domain)

            # Get last 10 documents
            documents_list = []
            if invoice_count > 0:
                invoices = (
                    request.env["account.move"]
                    .sudo()
                    .search(domain, order="invoice_date desc", limit=10)
                )
                for invoice in invoices:
                    documents_list.append({
                        "name": invoice.name,
                        "date": str(invoice.invoice_date),
                        "partner": invoice.partner_id.name if invoice.partner_id else "N/A",
                        "amount": invoice.amount_total,
                    })

            return invoice_count, documents_list
        except Exception as e:
            _logger.warning(f"Failed to count FT documents: {str(e)}")
            return 0, []

    def _count_fs_documents(self, company, year):
        """
        Count FS (Fatura Simplificada/Simplified Invoice) documents.
        Returns count and list of last 10 documents.

        :param company: Company record
        :param year: Year to check
        :return: Tuple (count, list_of_documents)
        """
        try:
            year_start = datetime(year, 1, 1).date()
            year_end = datetime(year, 12, 31).date()

            domain = [
                ("move_type", "=", "out_invoice"),
                ("document_type_id.code", "=", "FS"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", year_start),
                ("invoice_date", "<=", year_end),
                ("company_id", "=", company.id),
            ]

            # Get count
            invoice_count = request.env["account.move"].sudo().search_count(domain)

            # Get last 10 documents
            documents_list = []
            if invoice_count > 0:
                invoices = (
                    request.env["account.move"]
                    .sudo()
                    .search(domain, order="invoice_date desc", limit=10)
                )
                for invoice in invoices:
                    documents_list.append({
                        "name": invoice.name,
                        "date": str(invoice.invoice_date),
                        "partner": invoice.partner_id.name if invoice.partner_id else "N/A",
                        "amount": invoice.amount_total,
                    })

            return invoice_count, documents_list
        except Exception as e:
            _logger.warning(f"Failed to count FS documents: {str(e)}")
            return 0, []

    def _count_nc_documents(self, company, year):
        """
        Count NC (Nota de Crédito/Credit Note) documents.
        Returns count and list of last 10 documents.

        :param company: Company record
        :param year: Year to check
        :return: Tuple (count, list_of_documents)
        """
        try:
            year_start = datetime(year, 1, 1).date()
            year_end = datetime(year, 12, 31).date()

            domain = [
                ("move_type", "=", "out_refund"),
                ("document_type_id.code", "=", "NC"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", year_start),
                ("invoice_date", "<=", year_end),
                ("company_id", "=", company.id),
            ]

            # Get count
            credit_note_count = request.env["account.move"].sudo().search_count(domain)

            # Get last 10 documents
            documents_list = []
            if credit_note_count > 0:
                credit_notes = (
                    request.env["account.move"]
                    .sudo()
                    .search(domain, order="invoice_date desc", limit=10)
                )
                for credit_note in credit_notes:
                    documents_list.append({
                        "name": credit_note.name,
                        "date": str(credit_note.invoice_date),
                        "partner": credit_note.partner_id.name if credit_note.partner_id else "N/A",
                        "amount": credit_note.amount_total,
                    })

            return credit_note_count, documents_list
        except Exception as e:
            _logger.warning(f"Failed to count NC documents: {str(e)}")
            return 0, []

    def _count_pf_documents(self, company, year):
        """
        Count PF (Proforma) documents.
        Returns count and list of last 10 documents.

        :param company: Company record
        :param year: Year to check
        :return: Tuple (count, list_of_documents)
        """
        try:
            # Check if l10n_pt_sale module is installed (provides sale_type_id field)
            if not self._is_module_installed('l10n_pt_sale'):
                _logger.info("l10n_pt_sale module not installed - skipping PF document count")
                return 0, []

            # Check if sale_type_id field exists (v18+)
            if 'sale_type_id' not in request.env["sale.order"]._fields:
                _logger.info("sale_type_id field not found - skipping PF document count (v17 compatibility)")
                return 0, []

            year_start = datetime(year, 1, 1)
            year_end = datetime(year, 12, 31, 23, 59, 59)

            domain = [
                ("company_id", "=", company.id),
                ("date_order", ">=", year_start),
                ("date_order", "<=", year_end),
                ("sale_type_id.code", "=", "PF")
            ]

            # Get count
            proforma_count = request.env["sale.order"].sudo().search_count(domain)

            # Get last 10 documents
            documents_list = []
            if proforma_count > 0:
                proformas = (
                    request.env["sale.order"]
                    .sudo()
                    .search(domain, order="date_order desc", limit=10)
                )
                for proforma in proformas:
                    documents_list.append({
                        "name": proforma.name,
                        "date": str(proforma.date_order.date()) if proforma.date_order else "N/A",
                        "partner": proforma.partner_id.name if proforma.partner_id else "N/A",
                        "amount": proforma.amount_total,
                    })

            return proforma_count, documents_list
        except Exception as e:
            _logger.warning(f"Failed to count PF documents: {str(e)}")
            return 0, []

    def _count_or_documents(self, company, year):
        """
        Count OR (Orçamento/Quotation) documents.
        Returns count and list of last 10 documents.

        :param company: Company record
        :param year: Year to check
        :return: Tuple (count, list_of_documents)
        """
        try:
            # Check if l10n_pt_sale module is installed (provides sale_type_id field)
            if not self._is_module_installed('l10n_pt_sale'):
                _logger.info("l10n_pt_sale module not installed - skipping OR document count")
                return 0, []

            # Check if sale_type_id field exists (v18+)
            if 'sale_type_id' not in request.env["sale.order"]._fields:
                _logger.info("sale_type_id field not found - skipping OR document count (v17 compatibility)")
                return 0, []

            year_start = datetime(year, 1, 1)
            year_end = datetime(year, 12, 31, 23, 59, 59)

            domain = [
                ("company_id", "=", company.id),
                ("date_order", ">=", year_start),
                ("date_order", "<=", year_end),
                ("sale_type_id.code", "=", "OR")
            ]

            # Get count
            quotation_count = request.env["sale.order"].sudo().search_count(domain)

            # Get last 10 documents
            documents_list = []
            if quotation_count > 0:
                quotations = (
                    request.env["sale.order"]
                    .sudo()
                    .search(domain, order="date_order desc", limit=10)
                )
                for quotation in quotations:
                    documents_list.append({
                        "name": quotation.name,
                        "date": str(quotation.date_order.date()) if quotation.date_order else "N/A",
                        "partner": quotation.partner_id.name if quotation.partner_id else "N/A",
                        "amount": quotation.amount_total,
                    })

            return quotation_count, documents_list
        except Exception as e:
            _logger.warning(f"Failed to count OR documents: {str(e)}")
            return 0, []

    def _filter_templates_by_modules(self, templates, company, year, action='check'):
        """
        Filter templates based on installed modules, company configuration, and actual usage.
        Only include templates whose category requirements are met.

        Category/DocType -> Requirements mapping:
        - stock (GT): requires l10n_pt_stock module + company.l10n_pt_transport = True
        - sales (PF): requires actual usage in the relevant year
        - payments, sales (OR/FT/NC/RG), invoicing: always included

        :param templates: List of template dicts
        :param company: Company record to check configuration
        :param year: Year to check for document usage
        :param action: Action type ('check' or 'create') to determine which year to validate usage
        :return: Filtered list of templates
        """
        # Define category -> required module mapping
        category_modules = {
            'stock': 'l10n_pt_stock',
        }

        filtered = []
        for template in templates:
            category = template.get('category')
            doc_type_code = template.get('document_type_code')
            required_module = category_modules.get(category)

            # Check for PF (Proforma) usage
            if doc_type_code == 'PF':
                # Determine which year to check based on action
                if action == 'check':
                    # When checking, validate usage in the year being checked
                    year_to_check = year
                else:
                    # When creating, validate usage in previous year (what we'll copy from)
                    year_to_check = year - 1

                if not self._company_uses_proforma(company, year_to_check):
                    _logger.info(
                        f"Skipping template for {doc_type_code} "
                        f"({template['document_type_name']}) - "
                        f"company has no Proforma invoices in year {year_to_check}"
                    )
                    continue

            # Check for OR (Orçamento/Quotation) - requires l10n_pt_sale module
            if doc_type_code == 'OR':
                if not self._is_module_installed('l10n_pt_sale'):
                    _logger.info(
                        f"Skipping template for {doc_type_code} "
                        f"({template['document_type_name']}) - "
                        f"module l10n_pt_sale not installed"
                    )
                    continue

            # If no required module, include (after PF and OR checks above)
            if not required_module:
                filtered.append(template)
                continue

            # Check if required module is installed
            if not self._is_module_installed(required_module):
                _logger.info(
                    f"Skipping template for {doc_type_code} "
                    f"({template['document_type_name']}) - "
                    f"module {required_module} not installed"
                )
                continue

            # Additional company-specific checks
            if category == 'stock':
                # Check if company has transport documents enabled
                # v16: uses group_l10n_pt_transport (user group)
                # v17+: uses l10n_pt_transport (company field)

                # For v16: if module is installed, assume transport is enabled
                # (group check would require checking user permissions, not company config)
                if hasattr(company, 'l10n_pt_transport'):
                    # v17+ with company field
                    if not company.l10n_pt_transport:
                        _logger.info(
                            f"Skipping template for {doc_type_code} "
                            f"({template['document_type_name']}) - "
                            f"company transport documents not enabled (l10n_pt_transport=False)"
                        )
                        continue
                # If field doesn't exist (v16), module being installed is enough

            filtered.append(template)

        return filtered

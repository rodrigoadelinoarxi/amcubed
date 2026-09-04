# Arxi Quality Instance Client

## Overview

This module provides API endpoints for code metrics analysis and OpenAI-powered module documentation generation. It serves as a communication bridge between Odoo instances and external quality analysis tools.

## Main Features

- **Code Metrics Analysis**: Analyzes installed modules and calculates LOC (Lines of Code) using pygount
- **Module Categorization**: Separates Arxi modules from third-party modules
- **Migration Status**: Identifies migrated vs non-migrated modules based on version
- **Website Analysis**: Detects website-related functionality and customizations
- **Studio Customizations**: Reports on Odoo Studio fields, views, and models
- **OpenAI Integration**: Generates concise, factual descriptions of installed modules
- **Third-Party Integration Detection**: Identifies modules with external integrations

## API Endpoints

### `/api/uat/code_metrics` (POST)
Executes comprehensive code analysis including:
- LOC counts for Arxi and third-party modules
- JavaScript and XML file statistics
- Studio presence and customizations
- Website views and pages
- Multi-company detection
- OpenAI-powered module analysis

### `/api/uat/analyze_modules` (POST)
Analyzes specific modules and generates AI descriptions.

### `/api/uat/set_openai_key` (POST)
Configures the OpenAI API key for AI-powered features.

## Technical Details

- **Author**: Arxi
- **Version**: 17.0.0.0.5
- **Category**: Manufacturing/Quality
- **License**: OPL-1

# Portugal - E-Fatura Integration for Odoo 18.0

## Overview

This module integrates Odoo 18.0 with the Portuguese Tax Authority's E-Fatura system, allowing automatic import and management of electronic invoicing documents from suppliers.

**Version**: 18.0.0.0.1
**Author**: ARXILEAD
**License**: OPL-1 (Odoo Proprietary License)
**Status**: ✅ Production Ready

---

## 🎯 Features

### Core Functionality
- ✅ **Online Synchronization**: Direct connection to Tax Authority portal (Portal das Finanças)
- ✅ **Automatic Vendor Bill Creation**: Convert E-Fatura documents to Odoo vendor bills
- ✅ **Automatic Vendor Creation**: Create suppliers based on VAT number
- ✅ **Update Existing Bills**: Update E-Fatura metadata on existing invoices

### Smart Features
- ✅ **Mismatch Detection**: Automatic comparison between E-Fatura and Odoo amounts
- ✅ **Visual Warnings**: Yellow banner on invoices when discrepancies are detected
- ✅ **Intelligent Tax Mapping**: Multi-level tax lookup system
- ✅ **Per-Vendor Configuration**: Custom tax mappings per supplier
- ✅ **Document Status Tracking**: Track document status (Pending/Registered/Cancelled)

### Multi-Company
- ✅ **Company-Specific Settings**: Enable/disable E-Fatura per company
- ✅ **Independent Configuration**: Each company has its own tax mappings and credentials

---

## 📋 Requirements

### Odoo Version
- **Odoo 18.0** (Community or Enterprise)

### Odoo Module Dependencies
- `account` - Accounting module
- `base` - Base Odoo functionality
- `mail` - Mail threading

### Python Dependencies
```bash
pip3 install beautifulsoup4  # HTML parsing for AT portal
pip3 install html5lib         # HTML5 parser
pip3 install requests          # HTTP requests
```

---

## 📦 Installation

### 1. Install Python Dependencies
```bash
pip3 install beautifulsoup4 html5lib requests
```

### 2. Copy Module to Addons Directory
```bash
cp -r l10n_pt_efatura_import /path/to/odoo/addons/
```

### 3. Install Module in Odoo
1. Go to **Apps**
2. Click **Update Apps List**
3. Search for "E-Fatura"
4. Click **Install**

---

## ⚙️ Configuration

### A. Required Configuration

#### 1. Enable E-Fatura Integration
```
Settings > Accounting > E-Fatura > Enable E-Fatura Integration
```
- ✅ Check this box to activate all E-Fatura features
- ❌ When unchecked, the module is hidden and the import wizard is blocked

#### 2. Set Default Journal
```
Settings > Accounting > E-Fatura > Journal
```
- Select the purchase journal where E-Fatura invoices will be created
- Only "Purchase" type journals are allowed

#### 3. Online Sync Credentials
```
Settings > Companies > [Your Company] > Edit Company
```
Navigate to a tab where you can add:
- **AT API Username**: Your Portal das Finanças username
- **AT API Password**: Your Portal das Finanças password

⚠️ **Note**: These credentials are required for online synchronization

---

### B. Optional Configuration

#### 1. Default Tax Mappings (Company Level)
```
Settings > Accounting > E-Fatura > Default values for E-Fatura imports
```
Configure default taxes for:
- **Default E-Fatura Standard Tax**: Normal VAT rate (e.g., IVA 23%)
- **Default E-Fatura Intermediate Tax**: Intermediate rate (e.g., IVA 13%)
- **Default E-Fatura Reduced Tax**: Reduced rate (e.g., IVA 6%)
- **Default E-Fatura Exempt Tax**: Exempt/zero rate

💡 **Benefit**: Speeds up import and prevents invoice lines without taxes

#### 2. Per-Vendor Tax Mappings
```
Contacts > [Vendor] > Purchases Tab > E-Fatura Default Values
```
- Override company defaults for specific vendors
- Same fields as company-level configuration
- **Priority**: Vendor taxes > Company taxes

#### 3. Default Product
```
Settings > Accounting > E-Fatura > Default E-Fatura Product
```
- Product used for automatically created invoice lines

---

## 🚀 Usage

### Online Synchronization

```
1. Go to: Accounting > E-Fatura > Import E-Fatura
   ↓
2. Select date range (Date From / Date To)
   ↓
3. Click "Import" button
   ↓
4. System automatically:
   - Connects to Portal das Finanças
   - Authenticates with AT credentials
   - Fetches all documents for the period
   - Extracts document details (tax lines)
   - Creates/updates vendors automatically
   ↓
5. Wizard displays list of documents:
   - Checkbox to import each document
   - Shows: Date, Reference, Vendor, Type, Status, Base, VAT, Total
   - Indicates if invoice already exists
   ↓
6. Select documents and click "Create Vendor Bills"
   ↓
7. System creates/updates vendor bills
   ↓
8. Opens list view with created/updated invoices
```

### Viewing Discrepancies

When an invoice is created/updated with E-Fatura data:

1. **Yellow Banner**: Appears at the top if there are discrepancies
2. **Shows**:
   - Total: E-Fatura vs Invoice (difference in €)
   - VAT: E-Fatura vs Invoice (difference in €)
3. **Visual Indicators**: E-Fatura fields turn red in form view
4. **Resolution**: Adjust invoice lines until values match

---

## 📊 E-Fatura Metadata on Invoices

Each invoice stores the following E-Fatura metadata:

| Field | Description | Location |
|-------|-------------|----------|
| E-Fatura Reference | Document reference (e.g., FT 2024/123) | Other Info tab |
| E-Fatura Date | Original document date | Other Info tab |
| E-Fatura Vendor VAT | Supplier's VAT number | Other Info tab |
| E-Fatura Vendor Name | Supplier's name | Other Info tab |
| E-Fatura Type | Document type (FT, FR, NC, etc.) | Other Info tab |
| E-Fatura Status | Status (Pending/Registered/Cancelled) | Other Info tab |
| E-Fatura Tax Base | Tax base amount | Other Info tab |
| E-Fatura VAT Amount | VAT amount | Header (right panel) |
| E-Fatura Total | Total amount | Header (right panel) |
| E-Fatura AT ID | Tax Authority document ID | Other Info tab |

---

## 🔧 Technical Details

### Tax Mapping Hierarchy

When creating invoice lines, the system searches for taxes in this order:

1. **Configured Taxes** (fastest):
   - Vendor-specific tax configuration
   - Company-level tax configuration

2. **Exemption Code Search**:
   - Search by `exemption_id.code`
   - Search in tax name/description

3. **Tax Type Search**:
   - Search by `l10n_pt_tax_type` field
   - Search in tax name/description

4. **Percentage Search**:
   - Search by percentage only
   - Last resort fallback

5. **Not Found**:
   - Warning logged
   - Line created without tax

### Models

#### `account.move` (Extended)
E-Fatura metadata fields added to vendor bills.

**New Fields**:
- `imported_reference` - Document reference
- `imported_date` - Document date
- `imported_vendor_vat` - Vendor VAT
- `imported_vendor_name` - Vendor name
- `imported_doc_type` - Document type
- `imported_status` - Document status
- `imported_tax_base` - Tax base
- `imported_vat_amount` - VAT amount
- `imported_total` - Total amount
- `imported_tax_auth_doc_id` - AT document ID
- `imported_total_mismatch` - Total mismatch flag (computed)
- `imported_vat_mismatch` - VAT mismatch flag (computed)
- `imported_warning` - Warning message (computed)

#### `l10n_pt.dataport.import.efatura` (Transient)
Import wizard model.

**Key Methods**:
- `action_sync()` - Synchronize online with Portal das Finanças
- `action_import_selected()` - Create vendor bills from selected documents
- `_get_base_page(session)` - Login to AT portal
- `_get_period_docs(session)` - Fetch documents for period
- `_get_doc_lines(session, doc_id, doc_date)` - Fetch document lines
- `_create_wizard_line(doc, doc_lines)` - Create wizard line

#### `l10n_pt.dataport.import.efatura.line` (Transient)
Wizard line model for document selection.

**Key Methods**:
- `create_vendor_bill()` - Create or update vendor bill
- `_get_tax_from_line_data(tax_line)` - Intelligent tax lookup

#### `res.company` (Extended)
Company configuration for E-Fatura.

**New Fields**:
- `imported_enabled` - Enable/disable portal import
- `imported_journal_id` - Default journal
- `imported_tax_id` - Standard tax (23%)
- `imported_interm_tax_id` - Intermediate tax (13%)
- `imported_reduced_tax_id` - Reduced tax (6%)
- `imported_exempt_tax_id` - Exempt tax (0%)
- `imported_product_id` - Default product

#### `res.partner` (Extended)
Vendor-specific tax mappings.

**New Fields** (Property fields):
- `property_imported_tax_id` - Vendor standard tax
- `property_imported_interm_tax_id` - Vendor intermediate tax
- `property_imported_reduced_tax_id` - Vendor reduced tax
- `property_imported_exempt_tax_id` - Vendor exempt tax
- `property_imported_product_id` - Vendor default product

---

## 📁 Module Structure

```
l10n_pt_efatura_import/
├── __init__.py
├── __manifest__.py
├── README.md
│
├── models/
│   ├── __init__.py
│   ├── account_journal.py          # Journal extensions (minimal)
│   ├── account_move.py             # E-Fatura metadata on bills
│   ├── res_company.py              # Company settings
│   ├── res_config_setting.py       # Configuration interface
│   └── res_partner.py              # Partner tax mappings
│
├── wizards/
│   ├── __init__.py
│   ├── l10n_pt_dataport_import_efatura.py    # Import logic
│   └── l10n_pt_dataport_import_efatura.xml   # Import wizard UI
│
├── views/
│   ├── account_move_views.xml      # Warning banner + E-Fatura fields
│   ├── res_config_views.xml        # Settings page
│   └── res_partner_views.xml       # Partner E-Fatura tab
│
├── security/
│   ├── efatura_security.xml        # Security groups
│   └── ir.model.access.csv         # Access rights
│
├── static/
│   ├── description/
│   │   └── icon.png                # Module icon
│   └── src/
│       ├── js/
│       │   └── efatura_tree_extend.js      # List view extensions
│       └── xml/
│           └── efatura_list_button.xml     # Button templates
│
└── i18n/
    └── pt.po                       # Portuguese translations
```

---

## 🔐 Security

### Groups
- **E-Fatura User**: Access to E-Fatura menu and import functionality

### Access Rights
- E-Fatura wizard: User access (transient model)
- E-Fatura wizard lines: User access (transient model)

---

## 🐛 Troubleshooting

### Import Issues

#### "E-Fatura integration is not enabled"
**Solution**: Go to Settings > Accounting > E-Fatura and check "Enable E-Fatura Integration"

#### "No documents found for the selected period"
**Solution**:
- Verify date range
- Ensure documents exist in Portal das Finanças
- Check if you have documents for that period

#### "Failed to login to Tax Authority portal"
**Solution**:
- Verify AT credentials in company settings
- Ensure credentials have proper permissions on AT portal
- Check if AT portal is accessible

### Invoice Creation Issues

#### "No tax found for: X% / type: Y / exemption: Z"
**Solution**:
- Configure default tax mappings in Settings > Accounting > E-Fatura
- Create matching taxes in Accounting > Configuration > Taxes
- Configure vendor-specific taxes if needed

#### Lines created without taxes
**Solution**:
- Review warning in logs
- Configure appropriate tax mappings
- Manually add taxes to invoice lines

### Discrepancy Warnings

#### Yellow banner showing discrepancies
**This is normal** - Not an error, just a warning to review:
1. Compare E-Fatura amounts with invoice totals
2. Check invoice lines for correct prices/quantities
3. Verify tax rates are correct
4. Adjust as needed

---

## 💡 Best Practices

### ✅ Recommendations

1. **Configure Tax Mappings**: Set up default taxes to avoid lines without taxes
2. **Review Discrepancies**: Always check warnings before confirming invoices
3. **Vendor-Specific Taxes**: Configure for vendors with special regimes
4. **Test Before Production**: Test import with small date range first
5. **Secure Credentials**: Ensure AT credentials have limited access and proper permissions

### ⚠️ Important Notes

1. **Credentials**: AT credentials stored in database (use proper permissions)
2. **Update Behavior**: Only updates E-Fatura metadata, doesn't modify invoice lines
3. **Warnings**: Don't block invoice confirmation (just visual warnings)
4. **One-Way Sync**: Only imports from E-Fatura, doesn't export
5. **Real-Time**: Fetches data directly from Portal das Finanças

### 🚫 Limitations

1. **Vendor Bills Only**: This module only imports supplier invoices (not customer invoices)
2. **Odoo Version**: Requires Odoo 18.0
3. **Portugal Only**: Designed for Portuguese companies
4. **Manual Reconciliation**: Doesn't automatically reconcile payments
5. **No Emission**: Doesn't emit invoices to E-Fatura (import only)

---

## 🆘 Support

For issues, questions, or contributions:

- **Author**: ARXILEAD (https://arxi.pt)
- **License**: OPL-1 (Odoo Proprietary License)

---

## 📜 License

This module is licensed under the Odoo Proprietary License v1.0 (OPL-1).

**Restrictions**:
- Cannot be distributed without authorization
- Cannot be used in competing platforms
- Source code modifications allowed for own use only

For full license terms, see: https://www.odoo.com/documentation/user/legal/licenses.html

---

## 📝 Changelog

### Version 18.0.0.0.1 (2025-10-30)
- 🗑️ Removed CSV import functionality
- ✨ Webservice-only implementation
- 📝 Updated documentation

### Version 18.0.2.0.6 (2025-10-30)
- 🔧 Improved logging (removed excessive debug logs)
- 📝 Updated documentation
- ✅ Translations completed

### Version 18.0.2.0.5 (2025-10-30)
- 🌐 Internationalization: Warning messages moved to English with PT translations
- 📝 Translation improvements

### Version 18.0.2.0.4 (2025-10-30)
- ✨ Added enable/disable E-Fatura per company
- 🔒 Wizard blocked when E-Fatura is disabled
- 🎨 Settings hidden when E-Fatura is disabled

### Version 18.0.2.0.3 (2025-10-30)
- ⚠️ Added visual warning banner for discrepancies
- 🎨 Improved UI with color indicators
- 📊 Enhanced mismatch detection

### Version 18.0.2.0.2 (2025-10-30)
- 🗑️ Removed E-Fatura tags functionality
- 🧹 Code cleanup

### Version 18.0.2.0.1 (2025-10-30)
- 🗑️ Removed QR code functionality
- 📦 Removed pyzbar and Pillow dependencies
- 🧹 Code cleanup

### Version 18.0.2.0.0 (2025-10-30)
- 🎉 Initial refactored version for Odoo 18.0
- ✨ Online synchronization with Portal das Finanças
- ✨ Automatic vendor bill creation
- ✨ Intelligent tax mapping
- ✨ Mismatch detection
- ✨ Multi-company support

---

**Made with ❤️ for the Portuguese Odoo community**

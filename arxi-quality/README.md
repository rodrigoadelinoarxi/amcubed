# arxi-quality 17.0

Quality management system modules for Odoo 17.0 with SAFT-PT integration.

## Modules

### arxi_quality_saft_api_client
SAFT-PT API integration for quality control and compliance:
- Validates invoices, documents, and stock movements against SAFT-PT requirements
- Real-time validation with Portuguese Tax Authority (AT) rules
- Automated quality checks before document finalization
- Error tracking and resolution workflow

### arxi_quality_instance_client
Quality instance management:
- Multi-instance quality monitoring
- Client-specific quality configurations
- Quality metrics dashboard
- Instance health checks

## Deployment

### Using Git Subtree (Recommended)
Add to your Odoo server repository:
```bash
git subtree add -P arxi-quality git@github.com:arxi-team/arxi-quality.git 17.0 --squash
```

Update existing subtree:
```bash
git subtree pull -P arxi-quality git@github.com:arxi-team/arxi-quality.git 17.0 --squash
```

### Using Copy Script
From `server-saft_updates/_arxi_quality/`:
```bash
python copy_quality.py
```

## Configuration

### SAFT API Client
Navigate to Settings > Technical > System Parameters:
- `arxi_quality.saft_api_url` - SAFT validation API endpoint
- `arxi_quality.saft_api_key` - API authentication key
- `arxi_quality.enable_validation` - Enable/disable automatic validation

### Instance Client
Configure per-instance settings:
- Settings > Quality > Instance Configuration
- Set quality thresholds and alert rules
- Configure user roles and permissions

## Usage

### Document Validation
1. Create/edit invoice or document
2. Automatic SAFT validation runs before confirmation
3. Check validation status in Quality tab
4. Resolve errors if validation fails
5. Confirm document after passing validation

### Quality Monitoring
- View quality metrics: Quality > Dashboard
- Check instance health: Quality > Instance Status
- Review validation history: Quality > Validation Logs

## Troubleshooting

1. **Validation fails**: Check SAFT API connectivity and credentials
2. **Missing quality tabs**: Install and upgrade modules, restart Odoo
3. **API timeout errors**: Verify network connectivity to AT services
4. **Permission errors**: Assign quality manager role to users

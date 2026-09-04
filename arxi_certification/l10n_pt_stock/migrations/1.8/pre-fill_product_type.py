"""Fill empty product_type on categories before it becomes required (v19).

``product.category.product_type`` (the SAF-T inventory type, bloco K of the AT
inventory file — Portaria 2/2015 / 126/2019, "TEXTO 1 CARÁTER, deve ser
preenchido") is now ``required=True``. Older databases — including any migrated
from v18, where the field was never required — may hold categories with a NULL
product_type. Applying the NOT NULL column constraint on such data would abort
the upgrade, so this pre-migration fills the gaps with 'M' (Goods), the field's
own default and the neutral value that keeps the inventory file valid.

Runs as a PRE migration, before the ORM applies the NOT NULL constraint. 'M' is
a safe technical default; the correct per-product type stays the user's
responsibility (that is what required=True now enforces going forward).

Idempotent: once every category has a type, re-running changes nothing.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        # Fresh install: no pre-existing categories to backfill.
        return

    cr.execute(
        "UPDATE product_category SET product_type = 'M' WHERE product_type IS NULL"
    )
    if cr.rowcount:
        _logger.info(
            "l10n_pt_stock: filled product_type='M' on %s category(ies) with no "
            "SAF-T type before making the field required",
            cr.rowcount,
        )

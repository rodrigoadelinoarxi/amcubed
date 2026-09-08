from odoo import http, api, _, fields, SUPERUSER_ID
from odoo.http import Response, request
import subprocess
from odoo.exceptions import UserError
import ast
import json, os, logging
import difflib

SUCCESS_MESSAGE = _("Tests executed successfully on %s") % fields.Datetime.now()
RESPONSE = http.Response(
    json.dumps({"message": SUCCESS_MESSAGE}),
    status=200,
    headers={"Content-Type": "application/json"},
)
_logger = logging.getLogger(__name__)
ALWAYS_SKIP_FOLDERS = {
    "l10n_pt",
    "l10n_pt_ao",
    "l10n_pt_hr_payroll",
    "studio_customization",
    "arxi-quality",
    "arxi_quality_instance_client",
    "scripts",
    "arxi_certification",
    "ARXI_CERTIFICATION",
    "arxi_certification_patch",
    "ARXI_CERTIFICATION_PATCH",
}

IGNORED_MODULES = {"arxi_quality_instance_client", "studio_customization"}

SKIP_PREFIXES = ("ptplus",)


def _is_skipped(name):
    return (
            name in ALWAYS_SKIP_FOLDERS
            or name in IGNORED_MODULES
            or name.startswith(SKIP_PREFIXES)
    )


def search_for_website_in_python_files(module_path):
    website_related = []

    for root, dirs, files in os.walk(module_path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                with open(file_path, "r") as file_content:
                    content = file_content.read()
                    if "website=True" in content:
                        website_related.append(file_path)
    return website_related


def check_website_module(env):
    website_module = env["ir.module.module"].search([("name", "=", "website")])
    if website_module and website_module.state == "installed":
        _logger.info("The 'Website' module is installed and active.")
        return True
    else:
        _logger.warning(
            "The 'Website' module is not installed. No website-related functionality available."
        )
        return False


def _reset_to_original(view, original_arch):
    """Reset view architecture to original (hard reset)"""
    if original_arch and view.arch != original_arch:
        try:
            view.write({"arch": original_arch})
            return True
        except Exception as e:
            _logger.error("Failed to reset view %s: %s", view.id, e)
            return False
    return False


def _generate_differences(original, current):
    """Generate unified diff between original and current architecture"""
    if not original or not current or original == current:
        return None
    original_lines = original.splitlines(keepends=True)
    current_lines = current.splitlines(keepends=True)
    diff = list(
        difflib.unified_diff(
            original_lines,
            current_lines,
            fromfile="Original Architecture",
            tofile="Current Architecture",
            lineterm="",
        )
    )
    return "".join(diff) if diff else None


def count_loc_differences(differences):
    """Count actual lines of code differences from unified diff output"""
    if not differences:
        return 0
    # Split into lines and filter out diff headers
    lines = differences.split("\n")
    loc_lines = []
    for line in lines:
        line = line.strip()
        # Skip empty lines and diff headers
        if (
                line
                and not line.startswith("---")
                and not line.startswith("+++")
                and not line.startswith("@@")
                and not line.startswith("Index:")
        ):
            # Count actual code changes (lines starting with +, -, or containing actual content)
            if (
                    line.startswith("+") or line.startswith("-") or line.startswith(" ")
            ):  # Context lines
                loc_lines.append(line)
    return len(loc_lines)


def _get_original_architecture(self, view):
    """Get the original architecture from the first version of the view"""
    if not view:
        return None
    _logger.info("Processing view %s (%s)", view.id, view.name)
    # Try to get the original view from external ID (base module)
    external_id = view.get_external_id()
    _logger.info("External ID for view %s: %s", view.id, external_id)
    if external_id and external_id.get(view.id):
        xml_id = external_id[view.id]
        _logger.info("XML ID: %s", xml_id)
        if "." in xml_id:
            module, name = xml_id.split(".", 1)
            _logger.info("Module: %s, Name: %s", module, name)
            # Look for the original view in base modules
            try:
                original_view = self.env.ref(xml_id, raise_if_not_found=False)
                if original_view and original_view != view:
                    _logger.info(
                        "Found original view %s, different from current",
                        original_view.id,
                    )
                    return original_view.arch
                else:
                    _logger.info("Original view is same as current or not found")
            except Exception as e:
                _logger.info("Error getting original view: %s", e)
    # If no original found, try to find parent view
    if view.inherit_id:
        _logger.info(
            "Using inherit_id %s (%s) as original",
            view.inherit_id.id,
            view.inherit_id.name,
        )
        return view.inherit_id.arch
    # For website pages, try to find the base template
    if hasattr(view, "website_id") or "website" in view.name.lower():
        # Look for base website templates
        base_templates = self.env["ir.ui.view"].search(
            [
                ("name", "ilike", "website"),
                ("type", "=", "qweb"),
                ("active", "=", True),
                ("id", "!=", view.id),
            ],
            limit=1,
        )
        if base_templates:
            _logger.info(
                "Using base website template %s as original", base_templates[0].id
            )
            return base_templates[0].arch
    # Return None instead of current arch to force detection of differences
    _logger.info("No original architecture found for view %s", view.id)
    return None


def analyze_website_views(env, sample_limit=500):
    results = {
        "db_only": {"total": 0, "loc_total": 0, "sample": []},
        "normal": {"total": 0, "loc_total": 0, "sample": []},
        "summary": {
            "loc_db_only_total": 0,
            "loc_reset_total": 0,
            "loc_website_total": 0,
        },
    }

    IrUiView = env["ir.ui.view"].sudo()

    # --- DB-only views ---
    all_views = IrUiView.search(
        [("active", "=", True), ("type", "=", "qweb"), ("website_id", "!=", False)]
    )
    xmlids_map = all_views.get_external_id()

    db_only = [v for v in all_views if not xmlids_map.get(v.id)]
    results["db_only"]["total"] = len(db_only)

    for v in db_only[:sample_limit]:
        loc = len(v.arch.splitlines())
        results["db_only"]["loc_total"] += loc
        results["db_only"]["sample"].append(
            {
                "id": v.id,
                "name": v.name,
                "loc": loc,
                "arch_preview": v.arch[:200] + "..." if len(v.arch) > 200 else v.arch,
            }
        )

    # --- Normal website views with external_id ---
    with_xmlid = [v for v in all_views if xmlids_map.get(v.id)]
    results["normal"]["total"] = len(with_xmlid)

    for v in with_xmlid[:sample_limit]:
        original_arch = _get_original_architecture(v)
        if not original_arch or v.arch == original_arch:
            continue

        diffs = _generate_differences(original_arch, v.arch)
        loc_diff = count_loc_differences(diffs)
        results["normal"]["loc_total"] += loc_diff

        reset_ok = _reset_to_original(v, original_arch)

        results["normal"]["sample"].append(
            {
                "id": v.id,
                "name": v.name,
                "xml_id": xmlids_map.get(v.id),
                "has_changes": True,
                "loc_diff": loc_diff,
                "reset_performed": reset_ok,
            }
        )

    # --- Totais finais ---
    results["summary"]["loc_db_only_total"] = results["db_only"]["loc_total"]
    results["summary"]["loc_reset_total"] = results["normal"]["loc_total"]
    results["summary"]["loc_website_total"] = (
            results["db_only"]["loc_total"] + results["normal"]["loc_total"]
    )

    return results


def check_website_in_modules(env, modulos_not_migrados_instalados, target_dir):
    """
    Return a dict {module_name: [python_files_with_website_true]}.
    If the 'website' base module is not installed, return {}.
    """
    results = {}
    if not check_website_module(env):
        _logger.warning("Skipping website scan: base 'website' module not installed.")
        return results

    for mod in modulos_not_migrados_instalados:
        if mod["name"] in IGNORED_MODULES:
            continue

        module_path = None
        for root, dirs, files in os.walk(target_dir):
            if mod["name"] in dirs:
                module_path = os.path.join(root, mod["name"])
                break

        if not module_path:
            continue

        website_files = search_for_website_in_python_files(module_path)
        if website_files:
            _logger.info(
                "Website-related functionality found in third-party module %s",
                mod["name"],
            )
            _logger.info("Website-related Python files: %s", website_files)
            results[mod["name"]] = website_files

    return results


def _list_js_files(module_path: str):
    """Return a list of all .js files under module_path (recursively)."""
    js_files = []
    for root, _, files in os.walk(module_path):
        for f in files:
            if f.lower().endswith(".js"):
                js_files.append(os.path.join(root, f))
    return js_files


def js_stats_for_modules(modules):
    """
    modules: list of dicts like {'name': ..., 'path': ..., 'version': ...}
    Returns:
      stats_by_module: {module_name: {'files': N, 'minified': M, 'non_minified': N-M, 'has_js': bool, 'paths': [...]}}
      total_js_files: int
    """
    stats_by_module = {}
    total = 0
    for m in modules:
        path = m.get("path")
        if not path or not os.path.isdir(path):
            continue
        all_js = _list_js_files(path)
        count = len(all_js)
        minified = sum(p.lower().endswith(".min.js") for p in all_js)
        stats_by_module[m["name"]] = {
            "files": count,
            "minified": minified,
            "non_minified": count - minified,
            "has_js": count > 0,
            "paths": all_js,  # keep if you want the full list for debugging
        }
        total += count
    return stats_by_module, total


def archived_views_info(env, sample_limit=100):
    """
    Retorna vistas arquivadas (active=False), excluindo 'qweb', que têm model definido.
    """
    IrUiView = env["ir.ui.view"].sudo()
    views = IrUiView.search(
        [
            ("active", "=", False),
            ("type", "!=", "qweb"),
            ("model", "!=", False),
        ]
    )
    xmlids_map = views.get_external_id()
    sample = []

    for v in views[:sample_limit]:
        inherit_xml_id = None
        if v.inherit_id:
            inherit_xml_id = v.inherit_id.get_external_id().get(v.inherit_id.id)

        sample.append(
            {
                "id": v.id,
                "name": v.name,
                "xml_id": xmlids_map.get(v.id),
                "type": v.type,
                "model": v.model,
                "inherit_id": v.inherit_id.id if v.inherit_id else None,
                "inherit_xml_id": inherit_xml_id,
                "active": v.active,
            }
        )

    return {
        "archived_views_total": len(views),
        "sample": sample,
    }


def detect_installed_themes(target_dir, todos_modulos_instalados):
    """
    Verifica todos os módulos instalados e retorna uma lista dos que são temas,
    com base no campo 'category' do __manifest__.py, usando todos_modulos_instalados.
    """
    theme_modules = []

    for root, dirs, files in os.walk(target_dir):
        if "__manifest__.py" not in files:
            continue

        manifest_path = os.path.join(root, "__manifest__.py")
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = ast.literal_eval(f.read())
        except Exception as e:
            _logger.warning(f"Erro a ler manifest {manifest_path}: {e}")
            continue

        technical_name = os.path.basename(root)
        display_name = manifest.get("name", technical_name)
        category = manifest.get("category", "")

        _logger.info(
            f"Technical Name: {technical_name}, Display Name: {display_name}, Category: {category}"
        )

        if any(
                module["name"] == technical_name for module in todos_modulos_instalados
        ) and category.startswith("Theme/"):
            theme_modules.append(
                {
                    "name": technical_name,
                    "display_name": display_name,
                    "path": root,
                    "category": category,
                    "version": manifest.get("version"),
                    "author": manifest.get("author"),
                }
            )
            _logger.info(f"Found installed theme: {technical_name} ({display_name})")

    return theme_modules


def studio_views_info_strict(
        env, allowed_types=("form", "tree", "kanban", "search", "qweb"), sample_limit=100
):
    """
    Return ONLY Odoo Studio *customizations* whose xml_id starts with
    'studio_customization.odoo_studio_' and whose type is in allowed_types.
    """
    IrModelData = env["ir.model.data"].sudo()
    IrUiView = env["ir.ui.view"].sudo()

    # Directly fetch the Studio customization IMD rows → ir.ui.view ids
    imd = IrModelData.search(
        [
            ("module", "=", "studio_customization"),
            ("name", "ilike", "odoo_studio_%"),
            ("model", "=", "ir.ui.view"),
        ]
    )
    view_ids = [r.res_id for r in imd if r.res_id]
    views = IrUiView.browse(view_ids).exists()

    # Filter by allowed view types (as shown in your screenshots)
    views = views.filtered(lambda v: (v.type or "").lower() in allowed_types)

    # Build counts and a small sample
    by_type, by_model = {}, {}
    sample = []
    xmlids_map = views.get_external_id()  # {id: 'studio_customization.odoo_studio_*'}

    for v in views:
        vt = (v.type or "unknown").lower()
        vm = v.model or "unknown"
        by_type[vt] = by_type.get(vt, 0) + 1
        by_model[vm] = by_model.get(vm, 0) + 1

    for v in views[:sample_limit]:
        sample.append(
            {
                "id": v.id,
                "name": v.name,
                "xml_id": xmlids_map.get(v.id),
                "type": v.type,
                "model": v.model,
                "inherit_id": v.inherit_id and v.inherit_id.id,
                "inherit_xml_id": v.inherit_id
                                  and v.inherit_id.get_external_id().get(v.inherit_id.id),
                "mode": getattr(v, "mode", None),  # typically 'extension'
                "active": v.active,
            }
        )

    return {
        "has_studio_customizations": bool(views),
        "studio_customizations_total": len(views),
        "counts_by_type": by_type,  # e.g. {"form": 6, "tree": 4, "kanban": 1, ...}
        "counts_by_model": by_model,  # e.g. {"sale.order": 2, "crm.lead": 3, ...}
        "sample": sample,  # first N items for inspection
        "filter": {
            "module": "studio_customization",
            "name_prefix": "odoo_studio_",
            "allowed_types": list(allowed_types),
        },
    }


def studio_presence(env):
    """
    Returns a dict summarizing Odoo Studio elements present in DB:
      - whether web_studio is installed
      - total Studio fields
      - per-model breakdown
      - list of Studio-created models (x_studio_*)
    """
    IrModelFields = env["ir.model.fields"].sudo()
    IrModel = env["ir.model"].sudo()
    IrModule = env["ir.module.module"].sudo()

    # Studio app present?
    studio_mod = IrModule.search([("name", "=", "web_studio")], limit=1)
    studio_installed = bool(studio_mod and studio_mod.state == "installed")

    # All manual (custom) fields; then filter by Python prefix to avoid SQL wildcard issues.
    custom_fields = IrModelFields.search([("state", "=", "manual")])
    studio_fields = [f for f in custom_fields if (f.name or "").startswith("x_studio_")]

    # Per-model aggregation
    by_model = {}
    for f in studio_fields:
        model_name = f.model or (f.model_id and f.model_id.model) or "unknown"
        by_model.setdefault(model_name, []).append(
            {
                "name": f.name,
                "label": f.field_description,
                "ttype": f.ttype,
            }
        )

    # Optional: detect Studio-created models
    studio_models = IrModel.search([("model", "like", "x_studio_%")])
    studio_models_data = [{"model": m.model, "name": m.name} for m in studio_models]

    # Optional: counts-only view (handy for dashboards)
    counts_by_model = {m: len(fl) for m, fl in by_model.items()}

    return {
        "web_studio_installed": studio_installed,
        "has_studio_fields": len(studio_fields) > 0,
        "studio_fields_total": len(studio_fields),
        "studio_fields_by_model": by_model,  # detailed list per model
        "studio_counts_by_model": counts_by_model,  # compact counts per model
        "studio_models": studio_models_data,  # custom models created via Studio
    }


def _list_xml_files(module_path: str, strict_odoo_xml: bool = False):
    """
    Return a list of *.xml files under module_path (recursively).
    If strict_odoo_xml=True, only count files that look like Odoo data/view XML
    by scanning the first few KB for common Odoo tags.
    """
    xml_files = []
    for root, _, files in os.walk(module_path):
        for f in files:
            if f.lower().endswith(".xml"):
                p = os.path.join(root, f)
                if strict_odoo_xml:
                    try:
                        with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                            head = fh.read(4096)
                        if any(
                                tag in head
                                for tag in ("<odoo", "<data", "<record", "<template")
                        ):
                            xml_files.append(p)
                    except Exception:
                        xml_files.append(p)
                else:
                    xml_files.append(p)
    return xml_files


def xml_stats_for_modules(modules, strict_odoo_xml: bool = False):
    """
    modules: list like [{'name': ..., 'path': ..., 'version': ...}]
    Returns:
      stats_by_module: {module_name: {'files': N, 'has_xml': bool, 'paths': [...]}}
      total_xml_files: int
    """
    stats_by_module = {}
    total = 0
    for m in modules:
        path = m.get("path")
        if not path or not os.path.isdir(path):
            continue
        files = _list_xml_files(path, strict_odoo_xml=strict_odoo_xml)
        cnt = len(files)
        stats_by_module[m["name"]] = {
            "files": cnt,
            "has_xml": cnt > 0,
            "paths": files,  # drop this if you only want counts
        }
        total += cnt
    return stats_by_module, total


def multi_company_info(env, include_inactive=False, max_names=50):
    """
    Returns whether the DB is multi‑company based on res.company records.
    - include_inactive=False counts only active companies.
    - max_names limits how many company names we include in the payload.
    """
    domain = [] if include_inactive else [("active", "=", True)]
    companies = env["res.company"].sudo().search(domain)
    total = len(companies)
    data = {
        "is_multi_company": total > 1,
        "company_count": total,
        "count_basis": "active" if not include_inactive else "all",
    }
    if max_names and max_names > 0:
        data["companies"] = [
            {"id": c.id, "name": c.name} for c in companies[:max_names]
        ]
        if total > max_names:
            data["companies_truncated"] = True
    return data


def check_for_integration_with_3rd_party(modulos_not_migrados_instalados, target_dir):
    """
    Return a list of module names that have a 'controllers' directory.
    """
    modules_with_controllers = []

    for mod in modulos_not_migrados_instalados:
        module_path = None
        for root, dirs, files in os.walk(target_dir):
            if mod["name"] in dirs:
                module_path = os.path.join(root, mod["name"])
                break

        if not module_path:
            continue

        controllers_path = os.path.join(module_path, "controllers")
        if os.path.isdir(controllers_path):
            _logger.warning(
                "Module %s has integration with third-party services (controllers directory found).",
                mod["name"],
            )
            modules_with_controllers.append(mod["name"])

    return modules_with_controllers


def get_migrated_modules(target_dir, versao_nova):
    modulos_migrados, modulos_not_migrados = [], []
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if not _is_skipped(d)]

        module_name = os.path.basename(root)
        if _is_skipped(module_name):
            continue
        if "__manifest__.py" in files:
            manifest_path = os.path.join(root, "__manifest__.py")
            try:
                with open(manifest_path, "r") as fh:
                    manifest = ast.literal_eval(fh.read())
                module_version = manifest.get("version")
                module_name = os.path.basename(root)
                module_author = (manifest.get("author") or "").strip()
                module_data = {
                    "name": module_name,
                    "path": root,
                    "version": module_version,
                    "author": module_author,
                }
                if str(module_version).split(".")[0] == str(versao_nova).split(".")[0]:
                    modulos_migrados.append(module_data)
                else:
                    modulos_not_migrados.append(module_data)
            except Exception as e:
                _logger.warning(f"Erro a ler {manifest_path}: {e}")
    return modulos_migrados, modulos_not_migrados


def loc_per_module(modules, arxi_folders, other_folders):
    """
    Return {'arxi': {module_name: LOC}, 'third_party': {module_name: LOC}} categorizing modules,
    analyzing only modules that are in arxi_folders or other_folders.
    """
    arxi_modules = {}
    third_party_modules = {}

    relevant_modules = [
        m for m in modules if m["name"] in arxi_folders or m["name"] in other_folders
    ]

    for m in relevant_modules:
        module_name = m["name"]

        module_path = m.get("path")

        if not module_path or not os.path.isdir(module_path):
            continue

        # Run pygount directly on the module path
        cmd = [
            "/home/odoo/.local/bin/pygount",
            "--format=summary",
            "--suffix=py,xml,js",
            module_path,
        ]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
        )

        if res.returncode:
            _logger.warning("pygount failed for %s: %s", module_name, res.stderr[:200])
            continue

        loc_count = _extract_sum_code(res.stdout)

        if module_name in arxi_folders:
            arxi_modules[module_name] = loc_count
        elif module_name in other_folders:
            third_party_modules[module_name] = loc_count

    return {"arxi": arxi_modules, "third_party": third_party_modules}


def pygount_for_modules(modules):
    """
    Conta o total de LOC em todos os módulos indicados, usando pygount.
    modules: lista de dicts {'name': ..., 'path': ...}
    """
    total_loc = 0
    for mod in modules:
        name = mod.get("name")
        if _is_skipped(name):
            continue
        module_path = mod["path"]
        if not os.path.isdir(module_path):
            continue
        cmd = [
            "/home/odoo/.local/bin/pygount",
            "--format=summary",
            "--suffix=py,xml,js",
            module_path,
        ]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
        )
        if res.returncode != 0:
            _logger.warning(f"pygount failed for {module_path}: {res.stderr[:100]}")
            continue
        _logger.info(f"[pygount output for {module_path}]:\n{res.stdout}")
        # Procura a linha "│ Sum       │" e soma a coluna Code
        for line in res.stdout.splitlines():
            if "│ Sum" in line:
                parts = line.strip("│").split("│")
                # Normalmente: │ Sum │ 14 │ 100.0 │ 573 │ 64.2 │ 97 │ 10.9 │
                #                    0     1      2      3     4     5     6
                if len(parts) >= 4:
                    try:
                        code_col = int(parts[3].strip())
                        total_loc += code_col
                    except Exception:
                        pass
    return total_loc


def categorize_modules(target_directory):
    """
    Walk target_directory and return two lists:
      • arxi_folders   – modules whose manifest author is Arxi/ARXILEAD
      • other_folders  – everything else
    """
    arxi_folders, other_folders = [], []

    for root, dirs, files in os.walk(target_directory):
        dirs[:] = [d for d in dirs if not _is_skipped(d)]

        if "__manifest__.py" not in files:
            continue

        folder = os.path.basename(root)
        if _is_skipped(folder):
            continue

        manifest_path = os.path.join(root, "__manifest__.py")
        try:
            with open(manifest_path, "r", encoding="utf-8") as fh:
                manifest = ast.literal_eval(fh.read())
            author = (manifest.get("author") or "").strip().lower()
        except Exception as exc:
            _logger.error("Cannot read manifest %s: %s", manifest_path, exc)
            continue

        if author in {"arxi"}:
            arxi_folders.append(folder)
        if author not in {"arxi", "arxilead"}:
            other_folders.append(folder)

    return arxi_folders, other_folders


def _installed_module_names(env):
    """Return a set with the *technical names* of all installed modules."""
    return set(
        env["ir.module.module"].search([("state", "=", "installed")]).mapped("name")
    )


def _extract_sum_code(stdout: str) -> int:
    for line in stdout.splitlines():
        if "│ Sum" in line:
            parts = line.strip("│").split("│")
            if len(parts) >= 4:
                try:
                    return int(parts[3].strip())
                except Exception:
                    return 0
    return 0


def _skip_all_except(keep_name: str, arxi_folders, other_folders):
    return list(
        (set(arxi_folders) | set(other_folders) | ALWAYS_SKIP_FOLDERS | IGNORED_MODULES)
        - {keep_name}
    )


def infer_versao_nova_from_ignored_modules(target_dir, prefer_major=False):
    """
    Procura, em qualquer profundidade de target_dir, as pastas dos IGNORED_MODULES,
    lê o __manifest__.py e devolve a versão encontrada.
    Se prefer_major=True, devolve apenas o segmento 'major' (antes do primeiro ponto).
    """
    wanted = set(IGNORED_MODULES)
    found_versions = []

    for root, dirs, files in os.walk(target_dir):
        hits = wanted.intersection(dirs)
        for hit in hits:
            manifest_path = os.path.join(root, hit, "__manifest__.py")
            try:
                with open(manifest_path, "r", encoding="utf-8") as fh:
                    manifest = ast.literal_eval(fh.read())
                ver = (manifest.get("version") or "").strip()
                if ver:
                    ver_out = ver.split(".")[0] if prefer_major else ver
                    _logger.info("Detected version for %s: %s", hit, ver_out)
                    found_versions.append(ver_out)
            except Exception as e:
                _logger.warning("Erro a ler %s: %s", manifest_path, e)
            finally:
                wanted.discard(hit)
        if not wanted:
            break

    return found_versions[0] if found_versions else None


def run_pygount_analysis(skip_folders):
    to_skip = set(skip_folders or [])
    to_skip |= ALWAYS_SKIP_FOLDERS
    to_skip |= IGNORED_MODULES

    # Check for ARXILEAD modules and add them to skip list
    target_dir = "/home/odoo/src/user"
    for root, dirs, files in os.walk(target_dir):
        if "__manifest__.py" not in files:
            continue

        folder = os.path.basename(root)
        if folder in to_skip:
            continue
        if folder.startswith(SKIP_PREFIXES):
            to_skip.add(folder)
            continue

        manifest_path = os.path.join(root, "__manifest__.py")
        try:
            with open(manifest_path, "r", encoding="utf-8") as fh:
                manifest = ast.literal_eval(fh.read())
            author = (manifest.get("author") or "").strip().lower()
            if author == "arxilead":
                to_skip.add(folder)
        except Exception:
            continue

    """
    Launch pygount and return the CompletedProcess object.
    Passing an empty list analyses *all* folders.
    """
    cmd = [
        "/home/odoo/.local/bin/pygount",
        "--format=summary",
        "--suffix=py,xml,js",
    ]
    if to_skip:
        cmd.append(f"--folders-to-skip={','.join(sorted(to_skip))}")

    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=300,
        cwd="/home/odoo/src/user",
    )


def read_module_manifest_and_readme(module_path):
    """
    Read the __manifest__.py and README.md files from a module directory.
    Returns a dict with manifest content and readme content.
    """
    manifest_content = None
    readme_content = None

    # Read manifest
    manifest_path = os.path.join(module_path, "__manifest__.py")
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_content = f.read()
        except Exception as e:
            _logger.warning(f"Error reading manifest at {manifest_path}: {e}")

    # Read README.md
    readme_path = os.path.join(module_path, "README.md")
    if os.path.exists(readme_path):
        try:
            with open(readme_path, "r", encoding="utf-8") as f:
                readme_content = f.read()
        except Exception as e:
            _logger.warning(f"Error reading README at {readme_path}: {e}")

    return {"manifest": manifest_content, "readme": readme_content}


def call_openai_for_description(env, module_name, manifest_content, readme_content):
    """
    Call OpenAI API to generate a description of what the module does.
    Uses the arxi_openai_client module for API calls.
    """
    try:
        openai_client = env["arxi.openai.client"]
        description = openai_client.analyze_odoo_module(
            module_name=module_name,
            manifest_content=manifest_content,
            readme_content=readme_content,
            language="pt-PT",
        )
        return description
    except Exception as e:
        _logger.error(f"Error calling OpenAI API for module {module_name}: {e}")
        return f"Error generating description: {str(e)}"


class ArxiQualityApiUatClient(http.Controller):
    _webhook_partner = "/api/uat/res_partner"
    _webhook_project = "/api/uat/project_project"
    _webhook_task = "/api/uat/project_task"
    _webhook_sale = "/api/uat/sale_order"
    _webhook_invoice = "/api/uat/account_move"
    _webhook_product = "/api/uat/product"
    _webhook_hr_attendance = "/api/uat/hr_attendance"
    _webhook_document = "/api/uat/document"
    _webhook_code_metrics = "/api/uat/code_metrics"
    _webhook_set_openai_key = "/api/uat/set_openai_key"
    _webhook_analyze_modules = "/api/uat/analyze_modules"

    @http.route(
        _webhook_code_metrics, auth="none", type="http", methods=["POST"], csrf=False
    )
    def execute_code_metrics(self, **post):
        """
        Run pygount twice:
          • 'arxi'  : only Arxi/ARXILEAD modules
          • 'third' : only third-party modules
        """
        try:
            self.authenticate_token_and_environment(scope="code_metrics_access")
            if not post:
                try:
                    post = json.loads(request.httprequest.data.decode("utf-8"))
                except Exception as e:
                    post = {}
                    _logger.warning(
                        "Não foi possível fazer decode ao JSON do request: %s", e
                    )

            _logger.info("POST data: %s", post)
            _logger.info("POST data (after decode): %s", post)

            custom_tpls = (
                request.env["mail.template"]
                .sudo()
                .search([("template_category", "=", "custom_template")])
            )
            custom_tpls_data = [{"id": t.id, "name": t.name} for t in custom_tpls]
            custom_tpls_count = len(custom_tpls)
            _logger.info("custom_tpls_count: %s", custom_tpls_count)
            _logger.info("custom_tpls_data: %s", custom_tpls_data)

            target_dir = "/home/odoo/src/user"
            arxi_folders, other_folders = categorize_modules(target_dir)
            installed = _installed_module_names(request.env)
            versao_nova = post.get("versao_nova")
            if not versao_nova:
                raise UserError("versao_nova não fornecida.")

            versao_atual = infer_versao_nova_from_ignored_modules(
                target_dir, prefer_major=False
            )
            modulos_migrados, modulos_not_migrados = get_migrated_modules(
                target_dir, versao_nova
            )
            todos_modulos = modulos_migrados + modulos_not_migrados
            modulos_migrados_instalados = [
                m for m in modulos_migrados if m["name"] in installed
            ]
            modulos_not_migrados_instalados = [
                m for m in modulos_not_migrados if m["name"] in installed
            ]

            loc_migrados = pygount_for_modules(modulos_migrados_instalados)
            loc_not_migrados = pygount_for_modules(modulos_not_migrados_instalados)
            modulos_not_migrados_third_party_instalados = [
                m for m in modulos_not_migrados_instalados if m["name"] in other_folders
            ]

            loc_by_third_not_migrated = {}
            for m in modulos_not_migrados_third_party_instalados:
                skip = _skip_all_except(m["name"], arxi_folders, other_folders)
                res = run_pygount_analysis(skip)
                if res.returncode:
                    _logger.warning(
                        "pygount failed for %s: %s", m["name"], res.stderr[:200]
                    )
                    continue
                loc_by_third_not_migrated[m["name"]] = _extract_sum_code(res.stdout)

            loc_not_migrados_third_party = sum(loc_by_third_not_migrated.values())
            website_check = check_website_in_modules(
                request.env, todos_modulos, "/home/odoo/src/user"
            )
            _logger.info(
                "website_check modules: %s",
                ", ".join(sorted(website_check.keys())) or "none",
            )
            for mod_name, files in website_check.items():
                _logger.info("website_check %s -> %s", mod_name, files)

            third_party_integration = check_for_integration_with_3rd_party(
                todos_modulos, "/home/odoo/src/user"
            )
            _logger.info(
                "third_party_integration modules: %s",
                ", ".join(sorted(third_party_integration)) or "none",
            )
            todos_modulos_instalados = (
                    modulos_migrados_instalados + modulos_not_migrados_instalados
            )
            _logger.info("todos_modulos_instalados: %s", todos_modulos_instalados)
            js_stats_by_module, total_js_files = js_stats_for_modules(todos_modulos)
            loc_by_module = loc_per_module(todos_modulos, arxi_folders, other_folders)
            studio_info = studio_presence(
                request.env,
            )
            studio_views = studio_views_info_strict(
                request.env, allowed_types=("form", "tree", "kanban", "search")
            )
            _logger.info("studio_views: %s", studio_views)
            archived_views = archived_views_info(request.env)
            if check_website_module(request.env):
                published_pages_info = analyze_website_views(request.env)
            else:
                published_pages_info = {
                    "db_only": {"total": 0, "loc_total": 0, "sample": []},
                    "normal": {"total": 0, "loc_total": 0, "sample": []},
                    "summary": {
                        "loc_db_only_total": 0,
                        "loc_reset_total": 0,
                        "loc_website_total": 0,
                    },
                }

            _logger.info("Website published pages: %s", published_pages_info)

            _logger.info("archived_views: %s", archived_views)

            themes_instalados = detect_installed_themes(
                "/home/odoo/src/user", todos_modulos_instalados
            )
            _logger.info("Temas instalados: %s", [t["name"] for t in themes_instalados])

            xml_stats_by_module, xml_total_files = xml_stats_for_modules(
                todos_modulos, strict_odoo_xml=True
            )
            multi_company = multi_company_info(request.env, include_inactive=False)

            # OpenAI module analysis
            _logger.info("Starting OpenAI module analysis...")
            openai_module_analysis = []
            try:
                for module_data in todos_modulos_instalados:
                    module_name = module_data["name"]

                    # Skip ignored modules
                    if module_name in IGNORED_MODULES:
                        continue

                    module_path = module_data.get("path")
                    if not module_path:
                        _logger.warning(f"Module path not found for {module_name}")
                        continue

                    _logger.info(f"Analyzing module {module_name} with OpenAI...")

                    # Read manifest and README
                    files_content = read_module_manifest_and_readme(module_path)

                    # Get AI description
                    description = call_openai_for_description(
                        request.env,
                        module_name,
                        files_content["manifest"],
                        files_content["readme"],
                    )

                    openai_module_analysis.append(
                        {
                            "module_name": module_name,
                            "ai_description": description,
                            "has_readme": files_content["readme"] is not None,
                        }
                    )

                    _logger.info(
                        f"Generated description for module {module_name}: {description}"
                    )
            except Exception as e:
                _logger.error(f"Error in OpenAI module analysis: {e}")
                openai_module_analysis = []

            arxi_installed = [f for f in arxi_folders if f in installed]
            third_installed = [f for f in other_folders if f in installed]
            _logger.info("arxi_folders: %s", arxi_folders)
            _logger.info("other_folders: %s", other_folders)
            _logger.info("arxi_installed: %s", arxi_installed)
            _logger.info("third_installed: %s", third_installed)
            _logger.info("modulos_migrados: %s", modulos_migrados)
            _logger.info("modulos_not_migrados: %s", modulos_not_migrados)

            skip_for_arxi = list(
                (set(arxi_folders) - set(arxi_installed))
                | set(other_folders)
                | set(ALWAYS_SKIP_FOLDERS)
                | set(IGNORED_MODULES)
            )

            skip_for_third = list(
                (set(other_folders) - set(third_installed))
                | set(arxi_folders)
                | set(ALWAYS_SKIP_FOLDERS)
                | set(IGNORED_MODULES)
            )

            res_arxi = run_pygount_analysis(skip_for_arxi)
            if res_arxi.returncode:
                raise UserError(
                    _("pygount (arxi) failed %s: %s")
                    % (res_arxi.returncode, res_arxi.stderr[:200])
                )

            res_third = run_pygount_analysis(skip_for_third)
            if res_third.returncode:
                raise UserError(
                    _("pygount (third-party) failed %s: %s")
                    % (res_third.returncode, res_third.stderr[:200])
                )

            payload = {
                "status": "success",
                "generated_at": fields.Datetime.now().isoformat(),
                "metrics": {
                    "arxi": res_arxi.stdout,
                    "third": res_third.stdout,
                },
                "arxi_folders": arxi_folders,
                "other_folders": other_folders,
                "versao_atual": versao_atual,
                "third_installed": third_installed,
                "arxi_installed": arxi_installed,
                "loc_migrados": loc_migrados,
                "loc_not_migrados": loc_not_migrados,
                "modulos_not_migrados_versions": [
                    {"name": m["name"], "version": m.get("version", "unknown")}
                    for m in modulos_not_migrados
                ],
                "modulos_migrados_versions": [
                    {"name": m["name"], "version": m.get("version", "unknown")}
                    for m in modulos_migrados
                ],
                "modulos_migrados": [m["name"] for m in modulos_migrados_instalados],
                "modulos_not_migrados": [
                    m["name"] for m in modulos_not_migrados_instalados
                ],
                "loc_not_migrados_third_party": loc_not_migrados_third_party,
                "modulos_not_migrados_third_party_instalados": [
                    {
                        "name": m["name"],
                        "loc": loc_by_third_not_migrated.get(m["name"], 0),
                    }
                    for m in modulos_not_migrados_third_party_instalados
                ],
                "website_check": published_pages_info,
                "third_party_integration": third_party_integration,
                "loc_by_module": loc_by_module,
                "js_total_files": total_js_files,
                "js_stats_by_module": js_stats_by_module,
                "studio": studio_info,
                "studio_views": studio_views,
                "archived_views": archived_views,
                "xml_total_files": xml_total_files,
                "xml_stats_by_module": xml_stats_by_module,
                "multi_company": multi_company,
                "themes_instalados": themes_instalados,
                "website_published_pages": published_pages_info,
                "website_differences_loc": published_pages_info.get(
                    "comparison_info", {}
                ).get("total_loc_differences", 0),
                "custom_email_templates_count": custom_tpls_count,
                "custom_email_templates": custom_tpls_data,
                "openai_module_analysis": openai_module_analysis,
                "openai_modules_analyzed_count": len(openai_module_analysis),
            }

            return http.Response(
                json.dumps(payload),
                status=200,
                headers={"Content-Type": "application/json"},
            )

        except Exception as exc:
            _logger.error("Error in /code_metrics: %s", exc)
            return http.Response(
                json.dumps({"status": "error", "message": str(exc)}),
                status=500,
                headers={"Content-Type": "application/json"},
            )

    # Aux Methods
    def authenticate_token_and_environment(self, scope):
        auth_header = request.httprequest.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise UserError("Missing or invalid Authorization header.")

        token = auth_header.split(" ")[1]
        user_id = request.env["res.users.apikeys"]._check_credentials(
            scope=scope, key=token
        )
        if not user_id:
            raise UserError("Invalid or unauthorized token.")

        request.update_env(user=user_id)

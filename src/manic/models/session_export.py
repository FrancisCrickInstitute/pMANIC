"""
Session method export/import functionality.

Exports analytical methods and parameters only, requiring users to re-import
raw data during import. This ensures data integrity and scientific reproducibility
by maintaining the primacy of raw data while preserving analytical workflows.
"""

import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from manic.models.database import (
    get_connection,
    restore_compounds,
    restore_samples,
    soft_delete_compound,
    soft_delete_sample,
)
from manic.__version__ import __version__, APP_NAME
from manic.models.analysis import AnalysisMode
from manic.io.changelog_sections import (
    format_compounds_table_for_session_export,
    format_overrides_section_for_session_export,
)
from manic.processors.chromatographic_peak_deconvolution import (
    normalize_fit_type,
    normalize_noise_gate,
    normalize_stringency,
)

logger = logging.getLogger(__name__)


def export_session_method(
    export_path: str,
    analysis_mode: AnalysisMode | str = AnalysisMode.LABELLED,
) -> bool:
    """
    Export session methodology and parameters only (no processed data).

    Exports:
    - Compound definitions and parameters
    - Integration boundary overrides (session_activity)
    - Analysis methodology

    Does NOT export:
    - Raw CDF file data
    - Processed EIC data
    - Sample file paths

    This approach ensures scientific integrity by requiring users to
    re-import and reprocess raw data using the exported methodology.

    Args:
        export_path: Path where to save the method file

    Returns:
        True if export successful, False otherwise
    """
    try:
        export_path = Path(export_path)

        # Create manic_export directory structure
        if export_path.suffix.lower() == ".json":
            # Remove .json extension to use as base name
            base_name = export_path.stem
        else:
            base_name = export_path.name

        export_dir = export_path.parent / "manic_session_export"
        export_dir.mkdir(parents=True, exist_ok=True)

        # Set paths for JSON and changelog files with timestamp
        import datetime
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M')
        json_path = export_dir / f"{base_name}.json"
        changelog_path = export_dir / f"changelog_{timestamp}.md"

        mode = AnalysisMode.coerce(analysis_mode)
        method_data = {"analysis_mode": mode.value}

        with get_connection() as conn:
            # Export compound definitions and parameters
            compounds = []
            cursor = conn.execute("""
                SELECT compound_name, retention_time, loffset, roffset,
                       mass0, label_atoms, rt_tolerance, deleted,
                       baseline_correction, deconvolution_level,
                       deconvolution_fit_type, deconvolution_noise_gate,
                       amount_in_std_mix, int_std_amount, mm_files
                FROM compounds
                ORDER BY compound_name
            """)

            ion_rows = conn.execute(
                """
                SELECT compound_name, role, ordinal, mz,
                       expected_ratio, ratio_tolerance
                FROM compound_ions
                ORDER BY compound_name,
                         CASE role WHEN 'quantifier' THEN 0 ELSE 1 END,
                         ordinal
                """
            ).fetchall()
            ions_by_compound: dict[str, list[dict]] = {}
            for ion in ion_rows:
                ions_by_compound.setdefault(ion["compound_name"], []).append(
                    {
                        "role": ion["role"],
                        "ordinal": ion["ordinal"],
                        "mz": ion["mz"],
                        "expected_ratio": ion["expected_ratio"],
                        "ratio_tolerance": ion["ratio_tolerance"],
                    }
                )

            for row in cursor.fetchall():
                compounds.append(
                    {
                        "compound_name": row["compound_name"],
                        "retention_time": row["retention_time"],
                        "loffset": row["loffset"],
                        "roffset": row["roffset"],
                        "mass0": row["mass0"],
                        "label_atoms": row["label_atoms"],
                        "rt_tolerance": row["rt_tolerance"],
                        "ions": ions_by_compound.get(row["compound_name"], []),
                        "deleted": row["deleted"],
                        # Analytical method settings (part of reproducibility).
                        "baseline_correction": row["baseline_correction"],
                        "deconvolution_level": row["deconvolution_level"],
                        "deconvolution_fit_type": row["deconvolution_fit_type"],
                        "deconvolution_noise_gate": row["deconvolution_noise_gate"],
                        "amount_in_std_mix": row["amount_in_std_mix"],
                        "int_std_amount": row["int_std_amount"],
                        "mm_files": row["mm_files"],
                    }
                )

            method_data["compounds"] = compounds

            # Export session activity (integration overrides)
            session_overrides = []
            cursor = conn.execute("""
                SELECT compound_name, sample_name, retention_time, loffset, roffset
                FROM session_activity
                ORDER BY compound_name, sample_name
            """)

            for row in cursor.fetchall():
                session_overrides.append(
                    {
                        "compound_name": row["compound_name"],
                        "sample_name": row["sample_name"],
                        "retention_time": row["retention_time"],
                        "loffset": row["loffset"],
                        "roffset": row["roffset"],
                    }
                )

            method_data["session_overrides"] = session_overrides

            # Export deleted sample names
            cursor = conn.execute("""
                SELECT sample_name FROM samples WHERE deleted = 1 ORDER BY sample_name
            """)
            method_data["deleted_samples"] = [row["sample_name"] for row in cursor.fetchall()]

        # Add metadata
        method_data["export_metadata"] = {
            "export_date": datetime.datetime.now().isoformat(),
            "export_version": __version__,
            "application": APP_NAME,
            "analysis_mode": mode.value,
            "description": "Analytical method and parameters (raw data not included)",
        }

        # Write to JSON file
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(method_data, f, indent=2, ensure_ascii=False)

        # Generate human-readable changelog
        _generate_changelog(method_data, changelog_path)

        logger.info(f"Session method exported to {export_dir}")
        logger.info(f"JSON file: {json_path}")
        logger.info(f"Changelog: {changelog_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to export session method: {e}")
        return False


def import_session_overrides(
    import_path: str,
    expected_mode: AnalysisMode | str | None = None,
) -> tuple[bool, bool]:
    """
    Import session overrides from a method file.

    This should only be called after both compounds and CDF data have been loaded.
    It imports the session-specific integration boundary overrides and syncs
    the deleted state of compounds and samples.

    Args:
        import_path: Path to the method file to import

    Returns:
        Tuple of (success, has_deletion_data):
        - success: True if import successful, False otherwise
        - has_deletion_data: True if the file contained deletion info, False for legacy format
    """
    try:
        import_path = Path(import_path)

        if not import_path.exists():
            logger.error(f"Import file does not exist: {import_path}")
            return False, False

        # Load method data
        with open(import_path, "r", encoding="utf-8") as f:
            method_data = json.load(f)

        if expected_mode is not None:
            expected = AnalysisMode.coerce(expected_mode)
            exported_value = method_data.get("analysis_mode")
            exported = (
                AnalysisMode.coerce(exported_value)
                if exported_value is not None
                else AnalysisMode.LABELLED
            )
            if exported is not expected:
                logger.error(
                    "Session mode mismatch: file=%s current=%s",
                    exported.value,
                    expected.value,
                )
                return False, False

        # Import session overrides directly to database
        session_overrides = method_data.get("session_overrides", [])
        compounds = method_data.get("compounds", [])

        # Check if this is a legacy format (no deletion data)
        has_deletion_data = (
            any("deleted" in c for c in compounds) or
            "deleted_samples" in method_data
        )

        if has_deletion_data:
            # Sync compound deleted state with import
            compounds_to_restore = [c["compound_name"] for c in compounds if not c.get("deleted", 0)]
            compounds_to_delete = [c["compound_name"] for c in compounds if c.get("deleted", 0)]

            if compounds_to_restore:
                restored = restore_compounds(compounds_to_restore)
                if restored:
                    logger.info(f"Restored {restored} previously deleted compound(s)")

            for name in compounds_to_delete:
                soft_delete_compound(name)

            # Sync sample deleted state with import
            deleted_samples_in_import = set(method_data.get("deleted_samples", []))
            active_samples_in_import = {o["sample_name"] for o in session_overrides}

            samples_to_restore = list(active_samples_in_import - deleted_samples_in_import)
            if samples_to_restore:
                restored = restore_samples(samples_to_restore)
                if restored:
                    logger.info(f"Restored {restored} previously deleted sample(s)")

            for name in deleted_samples_in_import:
                soft_delete_sample(name)

        # Apply per-compound analytical method settings (deconvolution + baseline)
        # when the file provides them. Older method files omit these keys, so we
        # only update the columns actually present - this keeps import backward
        # compatible with files exported before these settings existed.
        _apply_compound_method_settings(compounds)
        _apply_compound_ions(compounds)

        if not session_overrides:
            logger.info("No session overrides to import")
            return True, has_deletion_data

        applied_count = 0
        skipped_count = 0

        with get_connection() as conn:
            for override in session_overrides:
                # Check if both compound and sample exist
                compound_exists = conn.execute(
                    "SELECT 1 FROM compounds WHERE compound_name = ?",
                    (override["compound_name"],),
                ).fetchone()

                sample_exists = conn.execute(
                    "SELECT 1 FROM samples WHERE sample_name = ?",
                    (override["sample_name"],),
                ).fetchone()

                if compound_exists and sample_exists:
                    # Apply the session override
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO session_activity
                        (compound_name, sample_name, retention_time, loffset, roffset, sample_deleted)
                        VALUES (?, ?, ?, ?, ?, 0)
                    """,
                        (
                            override["compound_name"],
                            override["sample_name"],
                            override["retention_time"],
                            override["loffset"],
                            override["roffset"],
                        ),
                    )
                    applied_count += 1
                else:
                    logger.warning(
                        f"Skipping session override for {override['compound_name']}/{override['sample_name']} - compound or sample not found"
                    )
                    skipped_count += 1

        logger.info(
            f"Imported {applied_count} session overrides, skipped {skipped_count}"
        )
        return True, has_deletion_data

    except Exception as e:
        logger.error(f"Failed to import session overrides: {e}")
        return False, False


def _apply_compound_method_settings(compounds: list) -> None:
    """Apply per-compound deconvolution/baseline settings from an imported method.

    Backward compatible: each setting is only written when the corresponding key
    is present in the file (older exports omit them), and only for compounds that
    already exist in the current database. Values are normalized so an unexpected
    or stale value falls back to a safe default.
    """
    if not compounds:
        return

    updated = 0
    with get_connection() as conn:
        for compound in compounds:
            name = compound.get("compound_name")
            if not name:
                continue

            assignments: list[str] = []
            values: list[Any] = []

            if "baseline_correction" in compound:
                assignments.append("baseline_correction = ?")
                values.append(1 if compound.get("baseline_correction") else 0)
            if "rt_tolerance" in compound:
                assignments.append("rt_tolerance = ?")
                values.append(compound.get("rt_tolerance"))
            if "deconvolution_level" in compound:
                assignments.append("deconvolution_level = ?")
                values.append(normalize_stringency(compound.get("deconvolution_level")))
            if "deconvolution_fit_type" in compound:
                assignments.append("deconvolution_fit_type = ?")
                values.append(normalize_fit_type(compound.get("deconvolution_fit_type")))
            if "deconvolution_noise_gate" in compound:
                assignments.append("deconvolution_noise_gate = ?")
                values.append(normalize_noise_gate(compound.get("deconvolution_noise_gate")))
            if "amount_in_std_mix" in compound:
                assignments.append("amount_in_std_mix = ?")
                values.append(compound.get("amount_in_std_mix"))
            if "int_std_amount" in compound:
                assignments.append("int_std_amount = ?")
                values.append(compound.get("int_std_amount"))
            if "mm_files" in compound:
                assignments.append("mm_files = ?")
                values.append(compound.get("mm_files"))

            if not assignments:
                continue

            values.append(name)
            cursor = conn.execute(
                f"UPDATE compounds SET {', '.join(assignments)} "
                "WHERE compound_name = ? AND deleted = 0",
                values,
            )
            if cursor.rowcount:
                updated += 1

    if updated:
        logger.info(f"Applied analytical method settings to {updated} compound(s)")


def _apply_compound_ions(compounds: list) -> None:
    """Restore explicit targeted-ion definitions from a method export."""

    with get_connection() as conn:
        for compound in compounds:
            name = compound.get("compound_name")
            ions = compound.get("ions")
            if not name or ions is None:
                continue
            exists = conn.execute(
                "SELECT 1 FROM compounds WHERE compound_name = ?",
                (name,),
            ).fetchone()
            if not exists:
                continue
            conn.execute(
                "DELETE FROM compound_ions WHERE compound_name = ?",
                (name,),
            )
            conn.executemany(
                """
                INSERT INTO compound_ions
                    (compound_name, role, ordinal, mz,
                     expected_ratio, ratio_tolerance)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        name,
                        ion["role"],
                        ion.get("ordinal", 0),
                        ion["mz"],
                        ion.get("expected_ratio"),
                        ion.get("ratio_tolerance"),
                    )
                    for ion in ions
                ],
            )


def validate_method_file(
    file_path: str,
    expected_mode: AnalysisMode | str | None = None,
) -> tuple[bool, Optional[str]]:
    """
    Validate that a file is a valid method export.

    Args:
        file_path: Path to the file to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        file_path = Path(file_path)

        if not file_path.exists():
            return False, "File does not exist"

        if file_path.stat().st_size == 0:
            return False, "File is empty"

        # Try to parse as JSON
        with open(file_path, "r", encoding="utf-8") as f:
            method_data = json.load(f)

        # Check required structure
        if not isinstance(method_data, dict):
            return False, "Invalid file format - not a JSON object"

        if "compounds" not in method_data:
            return False, "Missing compounds data"

        if expected_mode is not None:
            expected = AnalysisMode.coerce(expected_mode)
            file_mode = AnalysisMode.coerce(
                method_data.get("analysis_mode", AnalysisMode.LABELLED)
            )
            if file_mode is not expected:
                return (
                    False,
                    f"This is a {file_mode.display_name.lower()} method, but the "
                    f"current analysis is {expected.display_name.lower()}. "
                    "Start a new analysis in the matching mode.",
                )

        if not isinstance(method_data["compounds"], list):
            return False, "Compounds data is not a list"

        # Check if compounds have required fields
        compounds = method_data["compounds"]
        if compounds:
            required_fields = ["compound_name", "retention_time", "mass0"]
            first_compound = compounds[0]
            missing_fields = [
                field for field in required_fields if field not in first_compound
            ]

            if missing_fields:
                return (
                    False,
                    f"Compounds missing required fields: {', '.join(missing_fields)}",
                )

        return True, None

    except json.JSONDecodeError as e:
        return False, f"Invalid JSON format: {e}"
    except Exception as e:
        return False, f"Validation failed: {e}"


def get_method_info(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Get information about a method file.

    Args:
        file_path: Path to the method file

    Returns:
        Dictionary with method information or None if invalid
    """
    try:
        is_valid, error = validate_method_file(file_path)
        if not is_valid:
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            method_data = json.load(f)

        info = {}

        # Basic counts
        compounds = method_data.get("compounds", [])
        session_overrides = method_data.get("session_overrides", [])
        deleted_samples = method_data.get("deleted_samples", [])

        info["compound_count"] = len(compounds)
        info["session_override_count"] = len(session_overrides)

        # Get unique sample names from overrides
        unique_samples = set(override["sample_name"] for override in session_overrides)
        info["expected_sample_count"] = len(unique_samples)

        # Deletion data info
        deleted_compounds = [c for c in compounds if c.get("deleted", 0)]
        info["deleted_compound_count"] = len(deleted_compounds)
        info["deleted_sample_count"] = len(deleted_samples)
        info["has_deletion_data"] = (
            any("deleted" in c for c in compounds) or
            "deleted_samples" in method_data
        )

        # File size
        file_path = Path(file_path)
        info["file_size_kb"] = file_path.stat().st_size / 1024

        # Export metadata
        metadata = method_data.get("export_metadata", {})
        info["export_date"] = metadata.get("export_date", "Unknown")
        info["export_version"] = metadata.get("export_version", "Unknown")

        return info

    except Exception as e:
        logger.error(f"Failed to get method info: {e}")
        return None


def create_method_backup(backup_dir: Optional[str] = None) -> Optional[str]:
    """
    Create a backup of the current session method.

    Args:
        backup_dir: Directory to store backup, defaults to temp directory

    Returns:
        Path to backup file or None if failed
    """
    try:
        if backup_dir is None:
            backup_dir = tempfile.gettempdir()

        backup_dir = Path(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Generate backup filename with timestamp
        import datetime

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"manic_method_backup_{timestamp}.json"

        # Create backup
        if export_session_method(str(backup_path)):
            logger.info(f"Session method backup created: {backup_path}")
            return str(backup_path)
        else:
            return None

    except Exception as e:
        logger.error(f"Failed to create method backup: {e}")
        return None


def _generate_changelog(method_data: dict, changelog_path: Path) -> None:
    """
    Generate a human-readable changelog from method data.

    Args:
        method_data: The exported method data dictionary
        changelog_path: Path where to write the changelog file
    """
    try:
        with open(changelog_path, "w", encoding="utf-8") as f:
            # Header
            f.write("# MANIC Session Export Changelog\n\n")

            # Export metadata
            metadata = method_data.get("export_metadata", {})
            export_date = metadata.get("export_date", "Unknown")
            export_version = metadata.get("export_version", "Unknown")

            f.write(f"**Export Date:** {export_date}\n")
            f.write(f"**Export Version:** {export_version}\n")
            f.write(f"**Application:** {metadata.get('application', APP_NAME)}\n\n")
            f.write(
                f"**Analysis Mode:** {method_data.get('analysis_mode', 'labelled')}\n\n"
            )

            f.write("---\n\n")

            # Compounds section (shared formatter)
            compounds = method_data.get("compounds", [])
            f.write(format_compounds_table_for_session_export(compounds))

            # Session activity section (shared formatter)
            session_overrides = method_data.get("session_overrides", [])
            f.write(format_overrides_section_for_session_export(session_overrides))

            f.write("\n---\n\n")

            # Footer with instructions
            f.write("## Import Instructions\n\n")
            f.write("To use this exported session:\n\n")
            f.write(
                "1. **Load Compounds**: Use 'File → Load Compounds/Parameter List' to import compound definitions from the JSON file\n"
            )
            f.write(
                "2. **Load Raw Data**: Use 'File → Load Raw Data (CDF)' to import your CDF files\n"
            )
            f.write(
                "3. **Import Session**: Use 'File → Import Session...' to apply integration overrides\n\n"
            )

            f.write(
                "The JSON file contains the machine-readable data, while this changelog provides "
            )
            f.write(
                "a human-readable summary of the analytical session and any manual adjustments made.\n"
            )

        logger.info(f"Changelog generated: {changelog_path}")

    except Exception as e:
        logger.error(f"Failed to generate changelog: {e}")
        # Don't fail the entire export if changelog generation fails
        pass

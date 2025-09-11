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

from manic.models.database import get_connection
from manic.__version__ import __version__, APP_NAME
from manic.io.changelog_sections import (
    format_compounds_table_for_session_export,
    format_overrides_section_for_session_export,
)

logger = logging.getLogger(__name__)


def export_session_method(export_path: str) -> bool:
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

        # Set paths for JSON and changelog files
        json_path = export_dir / f"{base_name}.json"
        changelog_path = export_dir / "changelog.md"

        method_data = {}

        with get_connection() as conn:
            # Export compound definitions and parameters
            compounds = []
            cursor = conn.execute("""
                SELECT compound_name, retention_time, loffset, roffset,
                       mass0, label_atoms, deleted
                FROM compounds
                WHERE deleted = 0
                ORDER BY compound_name
            """)

            for row in cursor.fetchall():
                compounds.append(
                    {
                        "compound_name": row["compound_name"],
                        "retention_time": row["retention_time"],
                        "loffset": row["loffset"],
                        "roffset": row["roffset"],
                        "mass0": row["mass0"],
                        "label_atoms": row["label_atoms"],
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

        # Add metadata
        import datetime

        method_data["export_metadata"] = {
            "export_date": datetime.datetime.now().isoformat(),
            "export_version": __version__,
            "application": APP_NAME,
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


def import_session_overrides(import_path: str) -> bool:
    """
    Import session overrides from a method file.

    This should only be called after both compounds and CDF data have been loaded.
    It imports the session-specific integration boundary overrides.

    Args:
        import_path: Path to the method file to import

    Returns:
        True if import successful, False otherwise
    """
    try:
        import_path = Path(import_path)

        if not import_path.exists():
            logger.error(f"Import file does not exist: {import_path}")
            return False

        # Load method data
        with open(import_path, "r", encoding="utf-8") as f:
            method_data = json.load(f)

        # Import session overrides directly to database
        session_overrides = method_data.get("session_overrides", [])
        if not session_overrides:
            logger.info("No session overrides to import")
            return True

        applied_count = 0
        skipped_count = 0

        with get_connection() as conn:
            for override in session_overrides:
                # Check if both compound and sample exist
                compound_exists = conn.execute(
                    "SELECT 1 FROM compounds WHERE compound_name = ? AND deleted = 0",
                    (override["compound_name"],),
                ).fetchone()

                sample_exists = conn.execute(
                    "SELECT 1 FROM samples WHERE sample_name = ? AND deleted = 0",
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
        return True

    except Exception as e:
        logger.error(f"Failed to import session overrides: {e}")
        return False


def validate_method_file(file_path: str) -> tuple[bool, Optional[str]]:
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

        info["compound_count"] = len(compounds)
        info["session_override_count"] = len(session_overrides)

        # Get unique sample names from overrides
        unique_samples = set(override["sample_name"] for override in session_overrides)
        info["expected_sample_count"] = len(unique_samples)

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

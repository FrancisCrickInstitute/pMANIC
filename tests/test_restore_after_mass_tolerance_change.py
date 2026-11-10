import numpy as np
from netCDF4 import Dataset

from manic.io.eic_importer import regenerate_all_eics_with_mass_tolerance
from manic.models.database import (
    get_connection,
    get_deleted_compounds,
    get_deleted_samples,
    restore_compounds,
    restore_samples,
    soft_delete_compound,
    soft_delete_samples,
)
from manic.processors.eic_processing import get_eics_for_compound
from manic.ui.recovery_dialog import RecoveryDialog
from manic.utils.workers import MassToleranceReloadWorker


def _write_cdf(path):
    # m/z 100.75 joins channel 100 only above a 0.25 Da tolerance.
    with Dataset(path, "w") as cdf:
        cdf.createDimension("scan_number", 3)
        cdf.createDimension("point_number", 6)
        variables = {
            "scan_acquisition_time": ("scan_number", [294.0, 300.0, 306.0]),
            "scan_index": ("scan_number", [0, 2, 4]),
            "point_count": ("scan_number", [2, 2, 2]),
            "total_intensity": ("scan_number", [11.0, 11.0, 11.0]),
            "mass_values": ("point_number", [100.0, 100.75] * 3),
            "intensity_values": ("point_number", [1.0, 10.0] * 3),
        }
        for name, (dimension, values) in variables.items():
            cdf.createVariable(name, np.asarray(values).dtype, (dimension,))[:] = values


def _restore_first(kind, list_deleted, restore):
    dialog = RecoveryDialog(kind, list_deleted, restore)
    dialog.item_list.item(0).setSelected(True)
    dialog.restore_btn.click()


def _m0(compound, samples, use_corrected=False):
    return {
        eic.sample_name: np.round(eic.intensity[0], 4).tolist()
        for eic in get_eics_for_compound(compound, samples, use_corrected=use_corrected)
    }


def test_items_restored_after_a_tolerance_change_show_eics_at_the_new_tolerance(
    qapp, tmp_path
):
    with get_connection() as conn:
        for compound in ("Pyruvate", "Lactate"):
            conn.execute(
                "INSERT INTO compounds (compound_name, retention_time, mass0, "
                "label_atoms, formula) VALUES (?, 5.0, 100.0, 1, 'C6H12O3NSi')",
                (compound,),
            )
        for sample in ("s1", "s2"):
            _write_cdf(tmp_path / f"{sample}.cdf")
            conn.execute(
                "INSERT INTO samples (sample_name, file_name) VALUES (?, ?)",
                (sample, str(tmp_path / f"{sample}.cdf")),
            )
    regenerate_all_eics_with_mass_tolerance(0.2)
    assert _m0("Lactate", ["s1"]) == {"s1": [1.0, 1.0, 1.0]}

    soft_delete_compound("Pyruvate")
    soft_delete_samples(["s2"])
    MassToleranceReloadWorker(0.3).run()
    _restore_first("compound", get_deleted_compounds, restore_compounds)
    _restore_first("sample", get_deleted_samples, restore_samples)

    new_tolerance = [11.0, 11.0, 11.0]
    assert _m0("Pyruvate", ["s1", "s2"]) == {"s1": new_tolerance, "s2": new_tolerance}
    assert _m0("Lactate", ["s1", "s2"]) == {"s1": new_tolerance, "s2": new_tolerance}
    assert _m0("Pyruvate", ["s1", "s2"], use_corrected=True) == {
        "s1": [12.9016, 12.9016, 12.9016],
        "s2": [12.9016, 12.9016, 12.9016],
    }

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from manic.io.compound_reader import read_compound
from manic.io.compounds_import import (
    CompoundRow,
    UnlabelledCompoundRecord,
    import_compound_excel,
    insert_compound,
    insert_unlabelled_compound,
)
from manic.models import database
from manic.models.analysis import AnalysisMode, IonChannel, IonRole
from manic.models.database import soft_delete_compound
from manic.processors.chromatographic_peak_deconvolution import (
    DEFAULT_DECONVOLUTION_LEVEL,
)


SCHEMA = Path(__file__).parent.parent / "src" / "manic" / "models" / "schema.sql"


@pytest.fixture
def compound_db(tmp_path, monkeypatch):
    db_path = tmp_path / "add_compound.db"
    monkeypatch.setattr(database, "DB_FILE", db_path)
    with database.get_connection() as conn:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return db_path


def _labelled_row(**overrides) -> CompoundRow:
    values = dict(
        compound_name="Pyruvate",
        retention_time=6.37,
        mass0=174.0,
        loffset=0.1,
        roffset=0.15,
        label_atoms=3,
        formula="C3H4O3",
        label_type="C",
        tbdms=1,
        meox=0,
        me=0,
        amount_in_std_mix=10.0,
        int_std_amount=1.5,
        mm_files="*MM*",
    )
    values.update(overrides)
    return CompoundRow(**values)


def _unlabelled_record(**overrides) -> UnlabelledCompoundRecord:
    channels = (
        IonChannel(mz=273.0, role=IonRole.QUANTIFIER, ordinal=0),
        IonChannel(
            mz=147.0,
            role=IonRole.QUALIFIER,
            ordinal=1,
            expected_ratio=0.42,
            ratio_tolerance=0.25,
        ),
        IonChannel(mz=73.0, role=IonRole.QUALIFIER, ordinal=2),
    )
    values = dict(
        compound_name="Citrate 4TMS",
        retention_time=12.4,
        loffset=0.15,
        roffset=0.2,
        rt_window=0.25,
        amount_in_std_mix=8.0,
        int_std_amount=2.0,
        mm_files="*STD*",
        channels=channels,
    )
    values.update(overrides)
    return UnlabelledCompoundRecord(**values)


def _fetch_compound(name: str) -> dict:
    with database.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM compounds WHERE compound_name = ?", (name,)
        ).fetchone()
    assert row is not None
    return dict(row)


def test_labelled_insert_matches_import_column_set(compound_db, tmp_path):
    path = tmp_path / "labelled.csv"
    pd.DataFrame(
        [
            {
                "name": "Imported",
                "tR": 6.37,
                "Mass0": 174,
                "lOffset": 0.1,
                "rOffset": 0.15,
                "LabelAtoms": 3,
                "Formula": "C3H4O3",
                "LabelType": "C",
                "TBDMS": 1,
                "MeOX": 0,
                "Me": 0,
                "Amount in StdMix": 10.0,
                "Int Std amount": 1.5,
                "MM Files": "*MM*",
            }
        ]
    ).to_csv(path, index=False)
    assert import_compound_excel(path, AnalysisMode.LABELLED) == 1

    insert_compound(_labelled_row(compound_name="Inserted"))

    imported = _fetch_compound("Imported")
    inserted = _fetch_compound("Inserted")
    assert set(imported) == set(inserted)
    skip = {"id", "compound_name"}
    for key in imported:
        if key in skip:
            continue
        assert inserted[key] == imported[key]


def test_unlabelled_insert_writes_compound_ions_and_rt_tolerance(compound_db):
    insert_unlabelled_compound(_unlabelled_record())

    row = _fetch_compound("Citrate 4TMS")
    assert row["mass0"] == pytest.approx(273.0)
    assert row["label_atoms"] == 0
    assert row["formula"] is None
    assert row["label_type"] == "C"
    assert row["tbdms"] == 0
    assert row["meox"] == 0
    assert row["me"] == 0
    assert row["deconvolution_level"] == DEFAULT_DECONVOLUTION_LEVEL
    assert row["rt_tolerance"] == pytest.approx(0.25)
    assert row["amount_in_std_mix"] == pytest.approx(8.0)
    assert row["int_std_amount"] == pytest.approx(2.0)
    assert row["mm_files"] == "*STD*"

    compound = read_compound("Citrate 4TMS")
    assert compound.is_unlabelled_target
    assert [channel.mz for channel in compound.analysis_channels] == [273.0, 147.0, 73.0]
    assert [channel.role for channel in compound.analysis_channels] == [
        IonRole.QUANTIFIER,
        IonRole.QUALIFIER,
        IonRole.QUALIFIER,
    ]
    assert compound.analysis_channels[1].expected_ratio == pytest.approx(0.42)
    assert compound.analysis_channels[1].ratio_tolerance == pytest.approx(0.25)


def test_unlabelled_insert_defaults_rt_window_to_max_offset(compound_db):
    insert_unlabelled_compound(_unlabelled_record(rt_window=None, loffset=0.15, roffset=0.2))
    row = _fetch_compound("Citrate 4TMS")
    assert row["rt_tolerance"] == pytest.approx(0.2)


def test_duplicate_name_raises_value_error(compound_db):
    insert_compound(_labelled_row())
    with pytest.raises(ValueError, match="Pyruvate") as excinfo:
        insert_compound(_labelled_row())
    assert "recover deleted compounds" in str(excinfo.value)


def test_soft_deleted_name_raises_value_error(compound_db):
    insert_compound(_labelled_row())
    assert soft_delete_compound("Pyruvate")
    with pytest.raises(ValueError, match="Pyruvate") as excinfo:
        insert_compound(_labelled_row())
    assert "recover deleted compounds" in str(excinfo.value)


def test_blank_name_rejected():
    with pytest.raises(ValueError, match="blank"):
        CompoundRow(
            compound_name="   ",
            retention_time=1.0,
            mass0=100.0,
        )
    with pytest.raises(ValueError, match="blank"):
        insert_unlabelled_compound(_unlabelled_record(compound_name="   "))


def test_unlabelled_duplicate_nominal_mass_rejected():
    record = _unlabelled_record(
        channels=(
            IonChannel(mz=100.2, role=IonRole.QUANTIFIER, ordinal=0),
            IonChannel(mz=100.4, role=IonRole.QUALIFIER, ordinal=1),
        )
    )
    with pytest.raises(ValueError, match="nominal masses"):
        insert_unlabelled_compound(record)

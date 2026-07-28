from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from manic.io.compound_reader import read_compound
from manic.io.compounds_import import import_compound_excel
from manic.models import database
from manic.models.analysis import AnalysisMode, IonRole


SCHEMA = Path(__file__).parent.parent / "src" / "manic" / "models" / "schema.sql"


@pytest.fixture
def unlabelled_db(tmp_path, monkeypatch):
    db_path = tmp_path / "unlabelled.db"
    monkeypatch.setattr(database, "DB_FILE", db_path)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return db_path


def test_unlabelled_compound_import_stores_arbitrary_ion_channels(
    unlabelled_db, tmp_path
):
    compound_list = tmp_path / "targets.csv"
    pd.DataFrame(
        [
            {
                "name": "Citrate 4TMS",
                "tR": 12.4,
                "lOffset": 0.15,
                "rOffset": 0.2,
                "QIon": 273,
                "ValIon1": 147,
                "ValIon2": 73,
                "Qualifier 1 Ratio": 0.42,
                "Qualifier 1 Tolerance": 0.25,
            }
        ]
    ).to_csv(compound_list, index=False)

    count = import_compound_excel(
        compound_list,
        analysis_mode=AnalysisMode.UNLABELLED,
    )

    assert count == 1
    compound = read_compound("Citrate 4TMS")
    assert compound.is_unlabelled_target
    assert compound.label_atoms == 0
    assert compound.mass0 == 273
    assert compound.channel_count == 3
    assert [channel.mz for channel in compound.analysis_channels] == [273, 147, 73]
    assert [channel.role for channel in compound.analysis_channels] == [
        IonRole.QUANTIFIER,
        IonRole.QUALIFIER,
        IonRole.QUALIFIER,
    ]
    assert compound.analysis_channels[1].expected_ratio == pytest.approx(0.42)
    assert compound.analysis_channels[1].ratio_tolerance == pytest.approx(0.25)


def test_unlabelled_import_requires_quantifier_and_qualifier_columns(
    unlabelled_db, tmp_path
):
    compound_list = tmp_path / "labelled-shaped.csv"
    pd.DataFrame(
        [
            {
                "name": "Alanine",
                "tR": 3.2,
                "mass0": 116,
                "labelAtoms": 3,
                "lOffset": 0.1,
                "rOffset": 0.1,
            }
        ]
    ).to_csv(compound_list, index=False)

    with pytest.raises(ValueError, match="missing unlabelled column"):
        import_compound_excel(
            compound_list,
            analysis_mode=AnalysisMode.UNLABELLED,
        )

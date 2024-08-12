import pandas as pd
from src.manic.models import CompoundListData


def load_compound_list(file_path: str) -> CompoundListData:
    df = pd.read_excel(file_path)

    compound_data_object = CompoundListData(df["name"].tolist(), {})

    compound_data_object.compound_data = {
        row["name"]: {
            "tR": row["tR"],
            "Mass0": row["Mass0"],
            "lOffset": row["lOffset"],
            "rOffset": row["rOffset"],
        }
        for i, row in df.iterrows()
    }

    return compound_data_object

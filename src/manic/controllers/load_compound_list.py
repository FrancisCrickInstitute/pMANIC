import pandas as pd
from manic.models import CompoundListData, CompoundData
import logging

logger = logging.getLogger("manic_logger")


def load_compound_list(file_path: str) -> CompoundListData:
    df = pd.read_excel(file_path)

    compound_data_object = CompoundListData(df["name"].tolist(), [])

    compound_data_object.compound_data = [
        CompoundData(
            str(row["name"]),
            float(row["tR"]),
            float(row["Mass0"]),
            float(row["lOffset"]),
            float(row["rOffset"]),
        )
        for i, row in df.iterrows()
    ]

    logger.info(
        f"{len(compound_data_object.compound_data)} compounds have been loaded."
    )
    logger.info(
        f"See the list of loaded compounds {compound_data_object.compounds}"
    )
    logger.info(
        f"Check the following compound data objects: {vars(compound_data_object.compound_data[0])} and {vars(compound_data_object.compound_data[-1])}"
    )

    return compound_data_object

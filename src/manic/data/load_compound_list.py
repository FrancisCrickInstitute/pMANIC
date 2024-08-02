import pandas as pd


def load_compound_list(file_path: str) -> dict:
    # Read the Excel file
    df = pd.read_excel(file_path)
    # Create a dictionary of compound data from the dataframe
    compounds = {
        row["name"]: {
            "tR": row["tR"],
            "Mass0": row["Mass0"],
            "lOffset": row["lOffset"],
            "rOffset": row["rOffset"],
        }
        for i, row in df.iterrows()
    }

    return compounds

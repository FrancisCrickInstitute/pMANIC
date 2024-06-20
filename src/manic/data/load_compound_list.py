import pandas as pd
from src.manic.data.compound_data_object import Compound

def load_compound_list(file_path):
    # Read the Excel file
    df = pd.read_excel(file_path)
    # Create a list of Compound objects from the dataframe
    compounds = [
        Compound(row['name'], row['tR'], row['Mass0'], row['lOffset'], row['rOffset'])
        for _, row in df.iterrows()
    ]
    return compounds

from src.manic.data.compound_data_object import Compound
import pandas as pd

def load_compound_list(file_path):
    df = pd.read_excel(file_path, engine='openpyxl')
    compounds = [
        Compound(row['name'], row['tR'], row['Mass0'], row['lOffset'], row['rOffset'])
        for _, row in df.iterrows()
    ]
    return compounds
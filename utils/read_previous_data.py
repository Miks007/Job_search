import os
import pandas as pd
from datetime import datetime

def read_previous_data(file_path=None):
    """Reads previously scraped offers from the specified file path."""
    try:
        if file_path is None or not os.path.exists(file_path):
            return None, datetime.now()
        df = pd.read_excel(file_path)
        df['date_scraped'] = pd.to_datetime(df['date_scraped'])
        max_date_scraped = df['date_scraped'].max()
        return df, max_date_scraped
    except Exception as e:
        error_msg = f"Error during reading old data: {e}"
        raise Exception(error_msg)
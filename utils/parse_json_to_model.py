import json
from pydantic import BaseModel, ValidationError
from typing import Type, TypeVar, Optional
import logging

T = TypeVar("T", bound=BaseModel)

def parse_json_to_model(filename: str, model: Type[T]) -> Optional[T]:
    """
    Loads JSON from a file and validates it using a given Pydantic model.
    
    :param filename: Path to the JSON file.
    :param model: The Pydantic model class to validate the data.
    :return: An instance of the model if valid, otherwise None.
    """
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        return model(**data)
    except (json.JSONDecodeError, ValidationError) as e:
        logging.error(f"❌ Error loading JSON from {filename}: {e}")
        return None 

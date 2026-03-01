from pydantic import BaseModel
from typing import Dict, Any

class StateRequest(BaseModel):
    data: Dict[str, Any]

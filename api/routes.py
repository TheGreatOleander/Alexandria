
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any
from .hashchain import add_state, CHAIN, verify_chain

router = APIRouter()

class StateRequest(BaseModel):
    data: Dict[str, Any]

@router.post("/api/evolve")
def evolve(request: StateRequest):
    block = add_state(request.data)
    return block

@router.get("/api/replay")
def replay():
    return {"chain": CHAIN}

@router.get("/api/verify")
def verify():
    valid, index = verify_chain()
    return {"chain_valid": valid, "broken_at_index": index}

@router.get("/api/snapshot")
def snapshot():
    return {"chain": CHAIN, "length": len(CHAIN)}

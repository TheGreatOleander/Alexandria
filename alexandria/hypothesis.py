import hashlib
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

@dataclass
class Hypothesis:
    domain: str
    claim: str
    constraints: List[str]
    parameters: Dict[str, Any]
    derivation: str
    confidence: float
    meta: Dict[str, Any]

    def validate(self) -> bool:
        if not isinstance(self.domain, str) or not self.domain:
            return False
        if not isinstance(self.claim, str) or not self.claim:
            return False
        if not isinstance(self.constraints, list):
            return False
        if not isinstance(self.parameters, dict):
            return False
        if not isinstance(self.derivation, str):
            return False
        if not isinstance(self.confidence, float):
            return False
        if not (0.0 <= self.confidence <= 1.0):
            return False
        if not isinstance(self.meta, dict):
            return False
        return True

    def hash(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

import hashlib
import json
from datetime import datetime

CHAIN = []

def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"))

def compute_hash(index, timestamp, data, previous_hash):
    record = f"{index}{timestamp}{canonical(data)}{previous_hash}"
    return hashlib.sha256(record.encode()).hexdigest()

def add_state(data):
    index = len(CHAIN)
    timestamp = datetime.utcnow().isoformat()
    previous_hash = CHAIN[-1]["hash"] if CHAIN else "GENESIS"
    digest = compute_hash(index, timestamp, data, previous_hash)

    block = {
        "index": index,
        "timestamp": timestamp,
        "data": data,
        "previous_hash": previous_hash,
        "hash": digest
    }

    CHAIN.append(block)
    return block

def verify_chain():
    for i, block in enumerate(CHAIN):
        if i == 0:
            if block["previous_hash"] != "GENESIS":
                return False, i
        else:
            prev = CHAIN[i-1]
            if block["previous_hash"] != prev["hash"]:
                return False, i

        recalculated = compute_hash(
            block["index"],
            block["timestamp"],
            block["data"],
            block["previous_hash"]
        )

        if recalculated != block["hash"]:
            return False, i

    return True, None

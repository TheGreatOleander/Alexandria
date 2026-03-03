import json
import os
import hashlib
from datetime import datetime

LEDGER_FILE = "ledger.jsonl"

class Ledger:

    def __init__(self):
        if not os.path.exists(LEDGER_FILE):
            open(LEDGER_FILE, "w").close()

    def _get_last_hash(self):
        try:
            with open(LEDGER_FILE, "r") as f:
                lines = f.readlines()
                if not lines:
                    return None
                last = json.loads(lines[-1])
                return last.get("entry_hash")
        except:
            return None

    def commit(self, hypothesis, result):
        prev_hash = self._get_last_hash()

        entry = {
            "hypothesis_hash": hypothesis.hash(),
            "meta": hypothesis.meta,
            "result": result,
            "timestamp": datetime.utcnow().isoformat(),
            "prev_hash": prev_hash
        }

        entry_hash = hashlib.sha256(
            json.dumps(entry, sort_keys=True).encode()
        ).hexdigest()

        entry["entry_hash"] = entry_hash

        with open(LEDGER_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def verify_integrity(self):
        prev = None
        with open(LEDGER_FILE, "r") as f:
            for line in f:
                entry = json.loads(line)
                expected_hash = entry["entry_hash"]
                computed_hash = hashlib.sha256(
                    json.dumps({
                        k: entry[k] for k in entry if k != "entry_hash"
                    }, sort_keys=True).encode()
                ).hexdigest()

                if expected_hash != computed_hash:
                    return False

                if entry["prev_hash"] != prev:
                    return False

                prev = expected_hash

        return True
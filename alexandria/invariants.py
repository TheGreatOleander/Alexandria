# DOCTRINAL LOCK — DO NOT MODIFY AT RUNTIME

def check_invariants(hypothesis) -> bool:

    if hypothesis.confidence < 0.0 or hypothesis.confidence > 1.0:
        return False

    if len(hypothesis.claim) < 3:
        return False

    return True
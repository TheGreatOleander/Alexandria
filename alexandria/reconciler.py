# Basic contradiction detection + reconciliation scaffold

class Reconciler:

    def __init__(self):
        self.memory = {}

    def evaluate(self, hypothesis):
        domain = hypothesis.domain
        claim = hypothesis.claim

        if domain not in self.memory:
            self.memory[domain] = set()

        if claim in self.memory[domain]:
            return "ACCEPTED"

        # Simple contradiction check
        for existing in self.memory[domain]:
            if existing == f"NOT({claim})" or claim == f"NOT({existing})":
                return "REJECTED"

        self.memory[domain].add(claim)
        return "ACCEPTED"
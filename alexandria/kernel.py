from alexandria.invariants import check_invariants
from alexandria.reconciler import Reconciler
from alexandria.ledger import Ledger

class Kernel:

    def __init__(self):
        self.reconciler = Reconciler()
        self.ledger = Ledger()

    def evaluate(self, hypothesis):

        if not hypothesis.validate():
            result = "REJECTED"

        elif not check_invariants(hypothesis):
            result = "REJECTED"

        else:
            result = self.reconciler.evaluate(hypothesis)

        self.ledger.commit(hypothesis, result)
        return result
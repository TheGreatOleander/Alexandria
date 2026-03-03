# Sandbox-ready API adapter scaffold

import json
from alexandria.hypothesis import Hypothesis
from generators.interface import GeneratorAdapter

class APIAdapter(GeneratorAdapter):

    def propose(self):
        raise NotImplementedError("Implement provider call externally.")
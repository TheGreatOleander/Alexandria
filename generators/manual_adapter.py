import json
from alexandria.hypothesis import Hypothesis
from generators.interface import GeneratorAdapter

class ManualAdapter(GeneratorAdapter):

    def propose(self):
        with open("input.json", "r") as f:
            data = json.load(f)
        return Hypothesis(**data)
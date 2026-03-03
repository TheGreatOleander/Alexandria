# Example Ollama-compatible local adapter

import subprocess
import json
from alexandria.hypothesis import Hypothesis
from generators.interface import GeneratorAdapter

class LocalAdapter(GeneratorAdapter):

    def propose(self):

        prompt = "Return a valid Hypothesis JSON object."

        result = subprocess.run(
            ["ollama", "run", "llama3", prompt],
            capture_output=True,
            text=True
        )

        data = json.loads(result.stdout.strip())
        return Hypothesis(**data)
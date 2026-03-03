import argparse
import yaml
from alexandria.kernel import Kernel
from generators.manual_adapter import ManualAdapter
from generators.local_adapter import LocalAdapter
from generators.api_adapter import APIAdapter
from generators.tasker_bridge_adapter import TaskerBridgeAdapter
from generators.symbolic_adapter import SymbolicAdapter

GENERATORS = {
    "manual": ManualAdapter,
    "local": LocalAdapter,
    "api": APIAdapter,
    "bridge": TaskerBridgeAdapter,
    "symbolic": SymbolicAdapter
}

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--generator", type=str)
    parser.add_argument("--verify-ledger", action="store_true")
    args = parser.parse_args()

    config = yaml.safe_load(open("config/config.yaml"))
    gen_type = args.generator or config.get("generator")

    kernel = Kernel()

    if args.verify_ledger:
        print(kernel.ledger.verify_integrity())
        return

    adapter = GENERATORS[gen_type]()
    hypothesis = adapter.propose()

    result = kernel.evaluate(hypothesis)
    print(result)

if __name__ == "__main__":
    main()
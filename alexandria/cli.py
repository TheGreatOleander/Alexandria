"""
Alexandria Temporal Kernel — CLI

Usage:
    alexandria                     Print version and doctrine banner
    alexandria replay <ledger>     Replay a ledger file and report state
    alexandria report <ledger>     Full equilibrium report from a ledger file
    alexandria verify <ledger>     Verify all event hashes in a ledger file
    alexandria schema <ledger>     Infer schema proposals from a ledger file
"""

import json
import sys

from alexandria.kernel import TemporalKernel, Event, VERSION
from alexandria.persistence import LedgerStore
from alexandria.doctrine import print_doctrine_banner


def cmd_version():
    print_doctrine_banner()
    print(f"Version: {VERSION}")


def cmd_replay(path: str):
    store = LedgerStore()
    k = TemporalKernel()
    try:
        store.restore(k, path)
    except Exception as e:
        print(f"Replay failed: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Replayed {len(k.ledger)} events.")
    print(f"State keys: {sorted(k.state.keys())}")
    print(f"Snapshot hash: {k.snapshot_hash()}")


def cmd_report(path: str):
    store = LedgerStore()
    k = TemporalKernel()
    try:
        store.restore(k, path)
    except Exception as e:
        print(f"Failed: {e}", file=sys.stderr)
        sys.exit(1)
    report = k.equilibrium_report()
    print(json.dumps(report, indent=2, default=str))


def cmd_verify(path: str):
    """Verify cryptographic hashes of all events in a ledger file."""
    from alexandria.exceptions import LedgerCorruption
    try:
        with open(path) as f:
            records = json.load(f)
    except Exception as e:
        print(f"Could not read ledger: {e}", file=sys.stderr)
        sys.exit(1)

    ok = 0
    failed = 0
    for record in records:
        try:
            Event.from_dict(record)
            ok += 1
        except LedgerCorruption as e:
            print(f"CORRUPT: {e}", file=sys.stderr)
            failed += 1

    print(f"Verified {ok} events. Corrupted: {failed}.")
    if failed:
        sys.exit(1)


def cmd_schema(path: str):
    """Infer schema and relation proposals from a ledger file."""
    store = LedgerStore()
    k = TemporalKernel()
    try:
        store.restore(k, path)
    except Exception as e:
        print(f"Failed: {e}", file=sys.stderr)
        sys.exit(1)

    print("=== Position Proposals ===")
    for p in k.infer_schema(min_occurrence=2):
        print(" ", p.describe())

    print("\n=== Relation Proposals ===")
    for p in k.infer_relations(min_cooccurrence=3, min_confidence=0.8):
        print(" ", p.describe())
        print(f"    {p.constructor}")


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help", "help"):
        print(__doc__)
        return

    cmd = args[0]

    if cmd == "version" or cmd == "--version":
        cmd_version()
    elif cmd == "replay" and len(args) == 2:
        cmd_replay(args[1])
    elif cmd == "report" and len(args) == 2:
        cmd_report(args[1])
    elif cmd == "verify" and len(args) == 2:
        cmd_verify(args[1])
    elif cmd == "schema" and len(args) == 2:
        cmd_schema(args[1])
    else:
        print(f"Unknown command: {' '.join(args)}", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

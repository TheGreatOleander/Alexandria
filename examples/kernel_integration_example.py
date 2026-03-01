"""
Alexandria — Integration Example
=================================

A worked example showing how to integrate the Alexandria kernel
into an application startup sequence, and how to use the major
subsystems together.

Run with:
    python examples/kernel_integration_example.py
"""

from alexandria import TemporalKernel, Event, Lattice
from alexandria.relations import (
    SumRelation,
    RatioRelation,
    CategoricalImplicationRelation,
    ConditionalRelation,
    FunctionRelation,
    TemporalRelation,
)
from alexandria.invariants import (
    ValueMustBePositive,
    ValueNeverDecreases,
    RelationInvariant,
)
from alexandria.policies import PolicyChain, ConservativeWins, LastWriteWins
from alexandria.rules import RuleSet
from alexandria.doctrine import assert_doctrine_alignment, print_doctrine_banner


# ---------------------------------------------------------------------------
# 1. Doctrine check — verify configuration before startup
# ---------------------------------------------------------------------------

def startup(config: dict):
    print_doctrine_banner()
    assert_doctrine_alignment(config)
    print("Doctrine alignment verified.\n")


# ---------------------------------------------------------------------------
# 2. Define the lattice — the shape of what could exist
# ---------------------------------------------------------------------------

def build_lattice() -> Lattice:
    lattice = (
        Lattice()
        # Financial positions
        .define("fin", "costs",   {int, float}, description="Operating costs")
        .define("fin", "profit",  {int, float}, description="Net profit")
        .define("fin", "revenue", {int, float}, description="Total revenue")
        .define("fin", "margin",  {int, float}, description="Profit margin")
        # Pricing positions
        .define("pricing", "plan",       {str})
        .define("pricing", "rate_limit", {int})
        .define("pricing", "price",      {int, float})
    )

    # Attach a named ruleset — every inference is traceable to a proposition
    ruleset = (
        RuleSet("financial")
        .rule(
            "revenue_from_parts",
            SumRelation(["costs", "profit"], "revenue"),
            "Revenue equals costs plus profit",
        )
        .rule(
            "profit_margin",
            RatioRelation("profit", "revenue", "margin"),
            "Margin is profit divided by revenue",
        )
    )
    ruleset.attach_to(lattice)

    # Categorical implications — plan determines rate limit
    lattice.relate(CategoricalImplicationRelation("plan", "pro",        "rate_limit", 1_000))
    lattice.relate(CategoricalImplicationRelation("plan", "enterprise", "rate_limit", 100_000))

    return lattice


# ---------------------------------------------------------------------------
# 3. Build the kernel
# ---------------------------------------------------------------------------

def build_kernel(lattice: Lattice) -> TemporalKernel:
    return TemporalKernel(
        lattice=lattice,
        invariants=[
            ValueMustBePositive("revenue"),
            ValueMustBePositive("costs"),
            RelationInvariant(TemporalRelation("price", max_delta=50.0)),
        ],
        policy=PolicyChain(
            ConservativeWins(invariants=[
                ValueMustBePositive("revenue"),
            ]),
            LastWriteWins(),
        ),
    )


# ---------------------------------------------------------------------------
# 4. Main demonstration
# ---------------------------------------------------------------------------

def main():
    # Doctrine check
    startup({
        "time_model": "linear_singular",
        "branching_allowed": False,
    })

    lattice = build_lattice()
    k = build_kernel(lattice)

    # --- Apply some events ---
    print("=== Applying Events ===")
    k.apply(Event({"costs": 60.0, "profit": 40.0}, domain="fin"))
    print(f"revenue = {k.state['revenue']}")   # inferred: 100.0
    print(f"margin  = {k.state['margin']}")    # inferred: 0.4

    k.apply(Event({"plan": "enterprise"}, domain="pricing"))
    print(f"rate_limit = {k.state['rate_limit']}")  # inferred: 100000

    k.apply(Event({"price": 100.0}, domain="pricing"))
    k.apply(Event({"price": 140.0}, domain="pricing"))  # delta=40 < max=50, ok
    print(f"price = {k.state['price']}")

    # --- Provenance ---
    print("\n=== Provenance ===")
    print(k.explain("revenue"))
    for line in k.explain_chain("margin"):
        print(line)

    # --- Equilibrium report ---
    print("\n=== Equilibrium Report ===")
    report = k.equilibrium_report()
    print(f"Events applied:  {report['event_count']}")
    print(f"State keys:      {sorted(report['state_keys'])}")
    print(f"Solver energy:   {report['solver_energy']:.2e}")
    print(f"At equilibrium:  {report['at_equilibrium']}")
    print(f"Snapshot hash:   {report['snapshot_hash'][:16]}...")

    # --- Replay determinism ---
    print("\n=== Replay ===")
    h1 = k.snapshot_hash()
    k.replay()
    h2 = k.snapshot_hash()
    assert h1 == h2
    print(f"Replay hash matches: {h1[:16]}... ✓")

    # --- Schema inference ---
    print("\n=== Schema Inference ===")
    k2 = TemporalKernel()
    for i in range(1, 8):
        k2.apply(Event({
            "costs": float(i * 10),
            "profit": float(i * 5),
            "revenue": float(i * 15),
        }))
    proposals = k2.infer_relations(min_cooccurrence=3, min_confidence=0.9)
    for p in proposals:
        print(f"  {p.describe()}")


if __name__ == "__main__":
    main()

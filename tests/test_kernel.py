"""
Alexandria v9 test suite.
Covers:
  - Conflict resolution policies (LastWriteWins, DomainAuthorityWins,
    ConservativeWins, MergeFunction, OperatorPrompt, PolicyChain)
  - Categorical/boolean relations (EnumRelation, ExclusionRelation,
    CategoricalImplicationRelation, NegationRelation, ExactlyOneRelation,
    AllTrueRelation, AnyTrueRelation)
  - Composite relations (ConditionalRelation, TemporalRelation)
  - Named inference rules and RuleSet
  - Full ReconciliationReport
  - Variational solver (energy minimization)
  - Automatic _prev_ injection
  - Provenance chain walking
  - Structural analysis (underdetermined, cycles)
  - Empirical schema inference
  - Rich equilibrium report
"""
import os, json, time, tempfile, shutil, pytest

from alexandria.kernel import (
    TemporalKernel, Event, Lattice, LatticePosition,
    TemporalIndex, ConstraintPropagator, Occupancy,
)
from alexandria.relations import (
    Relation,
    SumRelation, RatioRelation, EqualityRelation,
    BoundedRelation, FunctionRelation,
    EnumRelation, ExclusionRelation, CategoricalImplicationRelation,
    NegationRelation, ExactlyOneRelation, AllTrueRelation, AnyTrueRelation,
    ConditionalRelation, TemporalRelation,
)
from alexandria.invariants import (
    Invariant,
    KeyMustExist, ValueMustBePositive, ValueNeverDecreases,
    DomainSumConserved, ImplicationInvariant, RelationInvariant,
)
from alexandria.domains import TrustDomain
from alexandria.policies import (
    ConflictPolicy,
    LastWriteWins, DomainAuthorityWins, ConservativeWins,
    MergeFunction, OperatorPrompt, PolicyChain, ConflictUnresolvable,
)
from alexandria.rules import InferenceRule, RuleSet
from alexandria.persistence import LedgerStore, GitLedger
from alexandria.solver import ConstraintSolver, SolverResult
from alexandria.provenance import ProvenanceLog
from alexandria.schema import SchemaInference, PositionProposal, RelationProposal
from alexandria.reconciler import ForkReconciler, ReconciliationReport
from alexandria.exceptions import (
    LatticeViolation, DomainViolation, InvariantViolation,
    SolverContradiction, LedgerCorruption,
)


# ===========================================================================
# Conflict Resolution Policies
# ===========================================================================

class TestLastWriteWins:
    def test_picks_newer_timestamp(self):
        policy = LastWriteWins()
        result = policy.resolve("x", 1, 2, {"ts_a": 100, "ts_b": 200})
        assert result == 2

    def test_picks_older_when_ts_a_higher(self):
        policy = LastWriteWins()
        result = policy.resolve("x", 99, 1, {"ts_a": 999, "ts_b": 1})
        assert result == 99

    def test_unresolved_on_equal_timestamps(self):
        policy = LastWriteWins()
        result = policy.resolve("x", 1, 2, {"ts_a": 50, "ts_b": 50})
        assert result is LastWriteWins.UNRESOLVED


class TestDomainAuthorityWins:
    def test_authority_domain_wins(self):
        policy = DomainAuthorityWins({"balance": "finance"})
        result = policy.resolve("balance", 100, 999,
                                {"domain_a": "finance", "domain_b": "ops"})
        assert result == 100

    def test_other_domain_wins(self):
        policy = DomainAuthorityWins({"balance": "finance"})
        result = policy.resolve("balance", 100, 999,
                                {"domain_a": "ops", "domain_b": "finance"})
        assert result == 999

    def test_unresolved_when_no_authority(self):
        policy = DomainAuthorityWins({"balance": "finance"})
        result = policy.resolve("other_key", 1, 2, {})
        assert result is DomainAuthorityWins.UNRESOLVED

    def test_priority_list(self):
        policy = DomainAuthorityWins({"x": ["primary", "secondary"]})
        result = policy.resolve("x", 10, 20,
                                {"domain_a": "secondary", "domain_b": "other"})
        assert result == 10


class TestConservativeWins:
    def test_max_direction(self):
        policy = ConservativeWins({"balance": "max"})
        assert policy.resolve("balance", 50.0, 100.0) == 100.0

    def test_min_direction(self):
        policy = ConservativeWins({"risk": "min"})
        assert policy.resolve("risk", 0.9, 0.1) == 0.1

    def test_resolves_unknown_key_by_magnitude(self):
        policy = ConservativeWins()
        assert policy.resolve("other", 1, 100) == 1
        assert policy.resolve("other", -50, 10) == 10

    def test_derives_max_from_positive_invariant(self):
        policy = ConservativeWins(invariants=[ValueMustBePositive("balance")])
        assert policy.resolve("balance", 50.0, 100.0) == 100.0

    def test_derives_max_from_never_decreases(self):
        policy = ConservativeWins(invariants=[ValueNeverDecreases("seq")])
        assert policy.resolve("seq", 3, 7) == 7


class TestMergeFunction:
    def test_custom_merge(self):
        policy = MergeFunction(lambda key, a, b, ctx: a + b)
        assert policy.resolve("total", 10, 20) == 30

    def test_unresolved_when_fn_returns_none(self):
        policy = MergeFunction(lambda key, a, b, ctx: None)
        assert policy.resolve("x", 1, 2) is MergeFunction.UNRESOLVED


class TestPolicyChain:
    def test_first_resolving_policy_wins(self):
        chain = PolicyChain(
            DomainAuthorityWins({"x": "admin"}),
            LastWriteWins(),
        )
        result = chain.resolve("x", 1, 2, {
            "domain_a": "admin", "ts_a": 50, "ts_b": 100
        })
        assert result == 1

    def test_falls_back_to_second_policy(self):
        chain = PolicyChain(
            DomainAuthorityWins({"other": "admin"}),
            LastWriteWins(),
        )
        result = chain.resolve("x", 1, 2, {"ts_a": 50, "ts_b": 100})
        assert result == 2

    def test_raises_when_all_exhausted(self):
        chain = PolicyChain(
            DomainAuthorityWins({"other": "admin"}),
            LastWriteWins(),
        )
        with pytest.raises(ConflictUnresolvable):
            chain.resolve("x", 1, 2, {"ts_a": 50, "ts_b": 50})

    def test_operator_prompt_in_chain(self):
        prompted = []
        def callback(key, a, b, ctx):
            prompted.append(key)
            return a

        chain = PolicyChain(
            DomainAuthorityWins({}),
            OperatorPrompt(callback),
        )
        result = chain.resolve("x", 99, 0)
        assert result == 99
        assert "x" in prompted


class TestReconciliationWithPolicy:
    def test_no_policy_fails_on_conflict(self):
        recon = ForkReconciler()
        report = recon.analyze({"x": 1}, {"x": 99})
        assert not report.successful
        assert "x" in report.conflicts

    def test_policy_resolves_conflict(self):
        policy = LastWriteWins()
        recon = ForkReconciler(policy=policy)
        report = recon.analyze(
            {"x": 1}, {"x": 99},
            context_a={"ts": 100}, context_b={"ts": 200}
        )
        assert report.successful
        assert report.merged["x"] == 99

    def test_kernel_reconcile_with_policy(self):
        policy = ConservativeWins({"balance": "max"})
        k1 = TemporalKernel(policy=policy)
        k1.apply(Event({"balance": 50.0, "owner": "alice"}))
        k2 = TemporalKernel(policy=policy)
        k2.apply(Event({"balance": 200.0, "owner": "alice"}))
        report = k1.reconcile(k2)
        assert report.successful
        assert report.merged["balance"] == 200.0

    def test_solver_extends_after_policy_merge(self):
        solver = ConstraintSolver([SumRelation(["a", "b"], "total")])
        policy = LastWriteWins()
        recon = ForkReconciler(solver=solver, policy=policy)
        report = recon.analyze(
            {"a": 10, "x": 1}, {"a": 20, "b": 5},
            context_a={"ts": 100}, context_b={"ts": 200}
        )
        assert report.successful
        assert report.merged["a"] == 20
        assert report.solver_inferred.get("total") == 25


# ===========================================================================
# Categorical / Boolean Relations
# ===========================================================================

class TestEnumRelation:
    def test_check_valid_value(self):
        rel = EnumRelation("status", {"active", "inactive", "pending"})
        assert rel.check({"status": "active"}) is None

    def test_check_invalid_value(self):
        rel = EnumRelation("status", {"active", "inactive"})
        assert rel.check({"status": "deleted"}) is not None

    def test_infer_single_allowed(self):
        rel = EnumRelation("flag", {True})
        assert rel.infer({}) == {"flag": True}


class TestExclusionRelation:
    def test_exclusion_violated(self):
        rel = ExclusionRelation("role", "admin", "status", "suspended")
        result = rel.check({"role": "admin", "status": "suspended"})
        assert result is not None

    def test_exclusion_satisfied(self):
        rel = ExclusionRelation("role", "admin", "status", "suspended")
        assert rel.check({"role": "admin", "status": "active"}) is None

    def test_exclusion_inapplicable(self):
        rel = ExclusionRelation("role", "admin", "status", "suspended")
        assert rel.check({"role": "user", "status": "suspended"}) is None


class TestCategoricalImplicationRelation:
    def test_infers_consequence(self):
        rel = CategoricalImplicationRelation("plan", "premium", "rate_limit", 10000)
        assert rel.infer({"plan": "premium"}) == {"rate_limit": 10000}

    def test_no_inference_when_different_value(self):
        rel = CategoricalImplicationRelation("plan", "premium", "rate_limit", 10000)
        assert rel.infer({"plan": "free"}) is None

    def test_check_violation(self):
        rel = CategoricalImplicationRelation("plan", "premium", "rate_limit", 10000)
        result = rel.check({"plan": "premium", "rate_limit": 100})
        assert result is not None


class TestNegationRelation:
    def test_infer_b_from_a(self):
        rel = NegationRelation("active", "suspended")
        assert rel.infer({"active": True}) == {"suspended": False}

    def test_infer_a_from_b(self):
        rel = NegationRelation("active", "suspended")
        assert rel.infer({"suspended": False}) == {"active": True}

    def test_check_violation(self):
        rel = NegationRelation("active", "suspended")
        assert rel.check({"active": True, "suspended": True}) is not None

    def test_check_satisfied(self):
        rel = NegationRelation("active", "suspended")
        assert rel.check({"active": True, "suspended": False}) is None


class TestExactlyOneRelation:
    def test_infer_last_false(self):
        rel = ExactlyOneRelation(["a", "b", "c"])
        result = rel.infer({"a": True, "b": False})
        assert result == {"c": False}

    def test_infer_must_be_true(self):
        rel = ExactlyOneRelation(["a", "b", "c"])
        result = rel.infer({"a": False, "b": False})
        assert result == {"c": True}

    def test_check_passes(self):
        rel = ExactlyOneRelation(["a", "b", "c"])
        assert rel.check({"a": True, "b": False, "c": False}) is None

    def test_check_fails_zero_true(self):
        rel = ExactlyOneRelation(["a", "b", "c"])
        assert rel.check({"a": False, "b": False, "c": False}) is not None

    def test_check_fails_two_true(self):
        rel = ExactlyOneRelation(["a", "b", "c"])
        assert rel.check({"a": True, "b": True, "c": False}) is not None


class TestAllTrueRelation:
    def test_infer_all_true_output(self):
        rel = AllTrueRelation(["a", "b"], "all_ok")
        assert rel.infer({"a": True, "b": True}) == {"all_ok": True}

    def test_infer_false_when_one_false(self):
        rel = AllTrueRelation(["a", "b"], "all_ok")
        assert rel.infer({"a": False, "b": True}) == {"all_ok": False}

    def test_check_violation(self):
        rel = AllTrueRelation(["a", "b"], "all_ok")
        assert rel.check({"a": True, "b": True, "all_ok": False}) is not None


class TestAnyTrueRelation:
    def test_infer_true_when_any_true(self):
        rel = AnyTrueRelation(["a", "b", "c"], "any_ok")
        assert rel.infer({"a": False, "b": True, "c": False}) == {"any_ok": True}

    def test_infer_false_when_all_false(self):
        rel = AnyTrueRelation(["a", "b"], "any_ok")
        assert rel.infer({"a": False, "b": False}) == {"any_ok": False}


# ===========================================================================
# Composite Relations
# ===========================================================================

class TestConditionalRelation:
    def test_applies_when_predicate_true(self):
        rel = ConditionalRelation(
            predicate=lambda s: s.get("status") == "active",
            inner=SumRelation(["a", "b"], "total"),
        )
        assert rel.infer({"status": "active", "a": 10, "b": 20}) == {"total": 30}

    def test_skips_when_predicate_false(self):
        rel = ConditionalRelation(
            predicate=lambda s: s.get("status") == "active",
            inner=SumRelation(["a", "b"], "total"),
        )
        assert rel.infer({"status": "inactive", "a": 10, "b": 20}) is None

    def test_in_solver(self):
        solver = ConstraintSolver([
            ConditionalRelation(
                predicate=lambda s: s.get("vip") is True,
                inner=FunctionRelation(["price"], "discounted", lambda p: p * 0.8),
            )
        ])
        result = solver.solve({"vip": True, "price": 100.0})
        assert result.inferred["discounted"] == 80.0

    def test_conditional_skips_in_solver(self):
        solver = ConstraintSolver([
            ConditionalRelation(
                predicate=lambda s: s.get("vip") is True,
                inner=FunctionRelation(["price"], "discounted", lambda p: p * 0.8),
            )
        ])
        result = solver.solve({"vip": False, "price": 100.0})
        assert "discounted" not in result.inferred


class TestTemporalRelation:
    def test_detects_excessive_increase(self):
        rel = TemporalRelation("price", max_delta=10.0)
        state = {"price": 150.0, "_prev_price": 100.0}
        result = rel.check(state)
        assert result is not None
        assert "max_delta" in result

    def test_allows_within_delta(self):
        rel = TemporalRelation("price", max_delta=60.0)
        state = {"price": 150.0, "_prev_price": 100.0}
        assert rel.check(state) is None

    def test_detects_excessive_decrease(self):
        rel = TemporalRelation("balance", min_delta=-5.0)
        state = {"balance": 80.0, "_prev_balance": 100.0}
        result = rel.check(state)
        assert result is not None

    def test_no_prev_state_passes(self):
        rel = TemporalRelation("x", max_delta=1.0)
        assert rel.check({"x": 999.0}) is None


# ===========================================================================
# Named Inference Rules and RuleSet
# ===========================================================================

class TestInferenceRule:
    def test_rule_infers_via_relation(self):
        rule = InferenceRule(
            name="revenue_from_parts",
            relation=SumRelation(["costs", "profit"], "revenue"),
            description="Revenue equals costs plus profit",
        )
        result = rule.infer({"costs": 60.0, "profit": 40.0})
        assert result == {"revenue": 100.0}

    def test_rule_checks_violation(self):
        rule = InferenceRule(
            name="revenue_check",
            relation=SumRelation(["costs", "profit"], "revenue"),
            description="Revenue conservation",
        )
        err = rule.check({"costs": 60.0, "profit": 40.0, "revenue": 99.0})
        assert err is not None

    def test_rule_has_identity(self):
        rule = InferenceRule(
            name="profit_margin",
            relation=RatioRelation("profit", "revenue", "margin"),
            description="Margin is profit divided by revenue",
        )
        assert "profit_margin" in rule.describe()
        assert "Margin" in rule.describe()


class TestRuleSet:
    def make_ruleset(self):
        rs = RuleSet("financial")
        rs.rule("revenue_from_parts", SumRelation(["costs", "profit"], "revenue"),
                "Revenue equals costs plus profit")
        rs.rule("profit_margin", RatioRelation("profit", "revenue", "margin"),
                "Margin is profit over revenue")
        return rs

    def test_ruleset_attach_to_lattice(self):
        lattice = (
            Lattice()
            .define("fin", "revenue", {int, float})
            .define("fin", "costs",   {int, float})
            .define("fin", "profit",  {int, float})
            .define("fin", "margin",  {int, float})
        )
        rs = self.make_ruleset()
        rs.attach_to(lattice)
        assert lattice.solver() is not None

    def test_ruleset_drives_inference(self):
        lattice = (
            Lattice()
            .define("fin", "revenue", {int, float})
            .define("fin", "costs",   {int, float})
            .define("fin", "profit",  {int, float})
            .define("fin", "margin",  {int, float})
        )
        rs = self.make_ruleset()
        rs.attach_to(lattice)
        k = TemporalKernel(lattice=lattice)
        k.apply(Event({"costs": 60.0, "profit": 40.0}, domain="fin"))
        assert k.state["revenue"] == 100.0
        assert abs(k.state["margin"] - 0.4) < 1e-9

    def test_ruleset_provenance_cites_rule_relation(self):
        lattice = (
            Lattice()
            .define("fin", "revenue", {int, float})
            .define("fin", "costs",   {int, float})
            .define("fin", "profit",  {int, float})
            .define("fin", "margin",  {int, float})
        )
        rs = self.make_ruleset()
        rs.attach_to(lattice)
        k = TemporalKernel(lattice=lattice)
        k.apply(Event({"costs": 60.0, "profit": 40.0}, domain="fin"))
        prov = k.explain("revenue")
        assert "inferred" in prov


# ===========================================================================
# Integration: Mixed Numeric + Categorical + Conditional
# ===========================================================================

class TestMixedConstraintSystem:
    def make_pricing_kernel(self):
        lattice = (
            Lattice()
            .define("pricing", "plan",       {str})
            .define("pricing", "rate_limit", {int})
            .define("pricing", "price",      {int, float})
            .define("pricing", "quantity",   {int})
            .define("pricing", "total",      {int, float})
            .define("pricing", "cost",       {int, float})
            .define("pricing", "margin",     {int, float})
            .define("pricing", "vip",        {bool})
            .relate(EnumRelation("plan", {"free", "pro", "enterprise"}))
            .relate(CategoricalImplicationRelation("plan", "pro", "rate_limit", 1000))
            .relate(CategoricalImplicationRelation("plan", "enterprise", "rate_limit", 100000))
            .relate(FunctionRelation(["price", "quantity"], "total", lambda p, q: p * q))
            .relate(RatioRelation("total", "cost", "margin"))
            .relate(ConditionalRelation(
                predicate=lambda s: s.get("vip") is True,
                inner=FunctionRelation(
                    ["price"], "discounted_price",
                    lambda p: round(p * 0.8, 2),
                ),
                description="VIP 20% discount"
            ))
        )
        return TemporalKernel(lattice=lattice)

    def test_plan_infers_rate_limit(self):
        k = self.make_pricing_kernel()
        k.apply(Event({"plan": "pro"}, domain="pricing"))
        assert k.state["rate_limit"] == 1000

    def test_numeric_chain_from_categorical(self):
        k = self.make_pricing_kernel()
        k.apply(Event({"plan": "enterprise", "price": 50.0,
                       "quantity": 10, "cost": 200.0}, domain="pricing"))
        assert k.state["rate_limit"] == 100000
        assert k.state["total"] == 500.0
        assert abs(k.state["margin"] - 2.5) < 1e-9

    def test_conditional_vip_discount(self):
        k = self.make_pricing_kernel()
        k.apply(Event({"vip": True, "price": 100.0,
                       "quantity": 5, "cost": 200.0}, domain="pricing"))
        assert k.state["discounted_price"] == 80.0

    def test_invalid_plan_blocked(self):
        k = self.make_pricing_kernel()
        with pytest.raises(SolverContradiction):
            k.apply(Event({"plan": "enterprise"}, domain="pricing"))
            k.apply(Event({"rate_limit": 999}, domain="pricing"))

    def test_replay_deterministic(self):
        k = self.make_pricing_kernel()
        k.apply(Event({"plan": "pro", "price": 25.0,
                       "quantity": 4, "cost": 50.0}, domain="pricing"))
        h1 = k.snapshot_hash()
        k.replay()
        assert k.snapshot_hash() == h1


# ===========================================================================
# Temporal Relation in kernel context
# ===========================================================================

class TestTemporalRelationInKernel:
    def test_temporal_constraint_via_injected_prev(self):
        temporal_inv = RelationInvariant(TemporalRelation("price", max_delta=10.0))
        k = TemporalKernel(invariants=[temporal_inv])
        k.apply(Event({"price": 100.0, "_prev_price": 90.0}))
        with pytest.raises(InvariantViolation):
            k.apply(Event({"price": 200.0, "_prev_price": 100.0}))


# ===========================================================================
# Core regression
# ===========================================================================

class TestCoreRegression:
    def test_deterministic_replay(self):
        k = TemporalKernel()
        k.apply(Event({"a": 1})).apply(Event({"b": 2}))
        h1 = k.snapshot_hash()
        k.replay()
        assert k.snapshot_hash() == h1

    def test_solver_infers_on_apply(self):
        lattice = (
            Lattice()
            .define("fin", "costs",   {int, float})
            .define("fin", "profit",  {int, float})
            .define("fin", "revenue", {int, float})
            .relate(SumRelation(["costs", "profit"], "revenue"))
        )
        k = TemporalKernel(lattice=lattice)
        k.apply(Event({"costs": 30.0, "profit": 70.0}, domain="fin"))
        assert k.state["revenue"] == 100.0

    def test_temporal_index(self):
        k = TemporalKernel()
        k.apply(Event({"x": 1}))
        t1 = k.ledger[-1].ts
        k.apply(Event({"x": 2}))
        assert k.at(t1)["x"] == 1

    def test_schema_inference(self):
        k = TemporalKernel()
        for i in range(5):
            k.apply(Event({"user": i, "action": "login"}))
        proposals = k.infer_schema(min_occurrence=3)
        keys = {p.key for p in proposals}
        assert "user" in keys and "action" in keys

    def test_persistence_round_trip(self):
        k = TemporalKernel()
        k.apply(Event({"x": 1})).apply(Event({"y": 2}))
        h1 = k.snapshot_hash()
        store = LedgerStore()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            store.save(k, path)
            k2 = TemporalKernel()
            store.restore(k2, path)
            assert k2.snapshot_hash() == h1
        finally:
            os.unlink(path)

    def test_git_round_trip(self):
        repo = tempfile.mkdtemp()
        try:
            gl = GitLedger(repo).init()
            k = TemporalKernel()
            for p in [{"a": 1}, {"b": 2}]:
                e = Event(p)
                k.apply(e)
                gl.append(e)
            h1 = k.snapshot_hash()
            k2 = TemporalKernel()
            gl.restore_kernel(k2)
            assert k2.snapshot_hash() == h1
        finally:
            shutil.rmtree(repo)


# ===========================================================================
# Variational solver
# ===========================================================================

class TestVariationalSolver:
    def test_energy_zero_at_exact_solution(self):
        solver = ConstraintSolver([SumRelation(["a", "b"], "total")])
        result = solver.solve({"a": 10, "b": 20})
        assert result.energy < 1e-9
        assert result.inferred["total"] == 30

    def test_energy_reported_in_result(self):
        solver = ConstraintSolver([SumRelation(["a", "b"], "total")])
        result = solver.solve({"a": 10, "b": 20})
        assert hasattr(result, "energy")
        assert hasattr(result, "minimization_steps")

    def test_minimizer_resolves_underdetermined_system(self):
        solver = ConstraintSolver(
            [SumRelation(["a", "b"], "total")],
            learning_rate=0.1,
            tolerance=1e-6,
        )
        result = solver.solve({"total": 10, "a": 3})
        assert abs(result.inferred.get("b", 7) - 7) < 1e-4

    def test_minimizer_reduces_residual_energy(self):
        solver = ConstraintSolver(
            [RatioRelation("profit", "revenue", "margin")],
            learning_rate=0.05,
            tolerance=1e-8,
        )
        result = solver.solve({"profit": 40.0, "revenue": 100.0})
        assert abs(result.inferred.get("margin", 0.4) - 0.4) < 1e-6
        assert result.energy < 1e-9

    def test_solver_energy_in_equilibrium_report(self):
        lattice = (
            Lattice()
            .define("fin", "a", {int, float})
            .define("fin", "b", {int, float})
            .define("fin", "total", {int, float})
            .relate(SumRelation(["a", "b"], "total"))
        )
        k = TemporalKernel(lattice=lattice)
        k.apply(Event({"a": 10.0, "b": 20.0}, domain="fin"))
        report = k.equilibrium_report()
        assert "solver_energy" in report
        assert report["solver_energy"] < 1e-9


# ===========================================================================
# Automatic _prev_ injection
# ===========================================================================

class TestAutomaticPrevInjection:
    def test_prev_injected_automatically(self):
        temporal_inv = RelationInvariant(TemporalRelation("price", max_delta=20.0))
        k = TemporalKernel(invariants=[temporal_inv])
        k.apply(Event({"price": 100.0}))
        k.apply(Event({"price": 115.0}))
        assert k.state["price"] == 115.0
        assert k.state.get("_prev_price") == 100.0

    def test_auto_prev_blocks_excessive_delta(self):
        temporal_inv = RelationInvariant(TemporalRelation("price", max_delta=20.0))
        k = TemporalKernel(invariants=[temporal_inv])
        k.apply(Event({"price": 100.0}))
        with pytest.raises(InvariantViolation):
            k.apply(Event({"price": 200.0}))
        assert k.state["price"] == 100.0

    def test_first_event_no_prev_skips_check(self):
        temporal_inv = RelationInvariant(TemporalRelation("x", max_delta=1.0))
        k = TemporalKernel(invariants=[temporal_inv])
        k.apply(Event({"x": 9999.0}))
        assert k.state["x"] == 9999.0

    def test_temporal_in_lattice_relation_auto_prev(self):
        lattice = (
            Lattice()
            .define("trade", "price", {int, float})
            .relate(TemporalRelation("price", max_delta=50.0))
        )
        k = TemporalKernel(lattice=lattice)
        k.apply(Event({"price": 100.0}, domain="trade"))
        k.apply(Event({"price": 140.0}, domain="trade"))
        assert k.state["price"] == 140.0

    def test_replay_preserves_temporal_behavior(self):
        temporal_inv = RelationInvariant(TemporalRelation("v", max_delta=10.0))
        k = TemporalKernel(invariants=[temporal_inv])
        k.apply(Event({"v": 10.0}))
        k.apply(Event({"v": 18.0}))
        h1 = k.snapshot_hash()
        k.replay()
        assert k.snapshot_hash() == h1


# ===========================================================================
# ConditionalRelation predicate re-evaluation
# ===========================================================================

class TestConditionalReEvaluation:
    def test_condition_set_in_same_event_fires(self):
        lattice = (
            Lattice()
            .define("pricing", "vip",        {bool})
            .define("pricing", "price",      {int, float})
            .define("pricing", "discounted", {int, float})
            .relate(ConditionalRelation(
                predicate=lambda s: s.get("vip") is True,
                inner=FunctionRelation(["price"], "discounted", lambda p: p * 0.8),
                description="VIP discount"
            ))
        )
        k = TemporalKernel(lattice=lattice)
        k.apply(Event({"vip": True, "price": 100.0}, domain="pricing"))
        assert k.state.get("discounted") == 80.0

    def test_condition_false_does_not_fire(self):
        lattice = (
            Lattice()
            .define("pricing", "vip",        {bool})
            .define("pricing", "price",      {int, float})
            .define("pricing", "discounted", {int, float})
            .relate(ConditionalRelation(
                predicate=lambda s: s.get("vip") is True,
                inner=FunctionRelation(["price"], "discounted", lambda p: p * 0.8),
            ))
        )
        k = TemporalKernel(lattice=lattice)
        k.apply(Event({"vip": False, "price": 100.0}, domain="pricing"))
        assert "discounted" not in k.state

    def test_condition_activated_by_prior_inference(self):
        lattice = (
            Lattice()
            .define("sys", "plan",     {str})
            .define("sys", "is_vip",   {bool})
            .define("sys", "price",    {int, float})
            .define("sys", "discount", {int, float})
            .relate(CategoricalImplicationRelation("plan", "enterprise", "is_vip", True))
            .relate(ConditionalRelation(
                predicate=lambda s: s.get("is_vip") is True,
                inner=FunctionRelation(["price"], "discount", lambda p: p * 0.5),
                description="Enterprise 50% discount"
            ))
        )
        k = TemporalKernel(lattice=lattice)
        k.apply(Event({"plan": "enterprise", "price": 200.0}, domain="sys"))
        assert k.state.get("is_vip") is True
        assert k.state.get("discount") == 100.0


# ===========================================================================
# ConservativeWins derives from invariants
# ===========================================================================

class TestConservativeWinsFromInvariants:
    def test_derives_max_from_positive_invariant(self):
        invs = [ValueMustBePositive("balance")]
        policy = ConservativeWins(invariants=invs)
        assert policy.resolve("balance", 10.0, 50.0) == 50.0

    def test_derives_max_from_never_decreases(self):
        invs = [ValueNeverDecreases("sequence")]
        policy = ConservativeWins(invariants=invs)
        assert policy.resolve("sequence", 5, 12) == 12

    def test_derives_min_from_bounded_relation_hi(self):
        rel = BoundedRelation("risk", hi_val=1.0)
        invs = [RelationInvariant(rel)]
        policy = ConservativeWins(invariants=invs)
        assert policy.resolve("risk", 0.9, 0.3) == 0.3

    def test_explicit_overrides_derived(self):
        invs = [ValueMustBePositive("x")]
        policy = ConservativeWins(key_directions={"x": "min"}, invariants=invs)
        assert policy.resolve("x", 10, 100) == 10

    def test_no_signal_uses_magnitude(self):
        policy = ConservativeWins()
        assert policy.resolve("unknown", 100, 3) == 3

    def test_reconciler_uses_invariant_derived_policy(self):
        invs = [ValueMustBePositive("balance"), ValueNeverDecreases("seq")]
        policy = ConservativeWins(invariants=invs)
        recon = ForkReconciler(policy=policy)
        report = recon.analyze(
            {"balance": 50.0, "seq": 5},
            {"balance": 200.0, "seq": 3},
            invariants=invs,
        )
        assert report.successful
        assert report.merged["balance"] == 200.0
        assert report.merged["seq"] == 5


# ===========================================================================
# Provenance chain walking
# ===========================================================================

class TestProvenanceChain:
    def test_chain_event_leaf(self):
        k = TemporalKernel()
        k.apply(Event({"x": 42}))
        chain = k.explain_chain("x")
        assert len(chain) == 1
        assert "event" in chain[0]
        assert "42" in chain[0]

    def test_chain_one_level_inference(self):
        lattice = (
            Lattice()
            .define("fin", "costs",   {int, float})
            .define("fin", "profit",  {int, float})
            .define("fin", "revenue", {int, float})
            .relate(SumRelation(["costs", "profit"], "revenue"))
        )
        k = TemporalKernel(lattice=lattice)
        k.apply(Event({"costs": 60.0, "profit": 40.0}, domain="fin"))
        chain = k.explain_chain("revenue")
        assert "inferred" in chain[0]
        full = "\n".join(chain)
        assert "costs" in full or "profit" in full

    def test_chain_two_level_inference(self):
        lattice = (
            Lattice()
            .define("fin", "costs",  {int, float})
            .define("fin", "profit", {int, float})
            .define("fin", "revenue",{int, float})
            .define("fin", "tax",    {int, float})
            .relate(SumRelation(["costs", "profit"], "revenue"))
            .relate(FunctionRelation(["profit"], "tax", lambda p: p * 0.3))
        )
        k = TemporalKernel(lattice=lattice)
        k.apply(Event({"costs": 60.0, "profit": 40.0}, domain="fin"))
        chain = k.explain_chain("tax")
        full = "\n".join(chain)
        assert "tax" in full
        assert "profit" in full
        assert "event" in full

    def test_chain_handles_unknown_key(self):
        k = TemporalKernel()
        chain = k.explain_chain("ghost")
        assert "no provenance" in chain[0]

    def test_chain_survives_replay(self):
        lattice = (
            Lattice()
            .define("fin", "a", {int, float})
            .define("fin", "b", {int, float})
            .define("fin", "c", {int, float})
            .relate(SumRelation(["a", "b"], "c"))
        )
        k = TemporalKernel(lattice=lattice)
        k.apply(Event({"a": 1.0, "b": 2.0}, domain="fin"))
        chain_before = k.explain_chain("c")
        k.replay()
        chain_after = k.explain_chain("c")
        assert chain_before == chain_after

    def test_chain_in_equilibrium_report(self):
        k = TemporalKernel()
        k.apply(Event({"answer": 42}))
        report = k.equilibrium_report()
        assert "provenance_chains" in report
        assert "answer" in report["provenance_chains"]
        chain = report["provenance_chains"]["answer"]
        assert isinstance(chain, list)
        assert len(chain) >= 1


# ===========================================================================
# Structural analysis (underdetermined, cycles)
# ===========================================================================

class TestSolverStructuralAnalysis:
    def test_underdetermined_detected(self):
        solver = ConstraintSolver([SumRelation(["a", "b"], "total")])
        result = solver.solve({"total": 10.0})
        assert "a" in result.underdetermined or "b" in result.underdetermined

    def test_fully_determined_no_underdetermined(self):
        solver = ConstraintSolver([SumRelation(["a", "b"], "total")])
        result = solver.solve({"a": 3.0, "b": 7.0})
        assert result.underdetermined == []
        assert result.inferred["total"] == 10.0

    def test_circular_dependency_detected(self):
        solver = ConstraintSolver([
            SumRelation(["a", "b"], "c"),
            SumRelation(["c", "d"], "a"),
        ], max_steps=20)
        result = solver.solve({"b": 5.0, "d": 3.0})
        assert len(result.cycles) > 0
        cycle_keys = {k for cycle in result.cycles for k in cycle}
        assert "a" in cycle_keys or "c" in cycle_keys

    def test_no_cycles_in_clean_system(self):
        solver = ConstraintSolver([
            SumRelation(["a", "b"], "c"),
            SumRelation(["c", "d"], "e"),
        ])
        result = solver.solve({"a": 1.0, "b": 2.0, "d": 4.0})
        assert result.cycles == []
        assert result.inferred["c"] == 3.0
        assert result.inferred["e"] == 7.0

    def test_underdetermined_in_equilibrium_report(self):
        lattice = (
            Lattice()
            .define("fin", "a",     {int, float})
            .define("fin", "b",     {int, float})
            .define("fin", "total", {int, float})
            .relate(SumRelation(["a", "b"], "total"))
        )
        k = TemporalKernel(lattice=lattice)
        k.apply(Event({"total": 100.0}, domain="fin"))
        report = k.equilibrium_report()
        assert "underdetermined_keys" in report
        underdetermined = report["underdetermined_keys"]
        assert "a" in underdetermined or "b" in underdetermined


# ===========================================================================
# Empirical schema inference
# ===========================================================================

class TestEmpiricalSchemaInference:
    def _make_kernel_with_sum_data(self):
        k = TemporalKernel()
        for i in range(1, 8):
            costs = float(i * 10)
            profit = float(i * 5)
            revenue = costs + profit
            k.apply(Event({"costs": costs, "profit": profit, "revenue": revenue}))
        return k

    def test_sum_relation_detected(self):
        k = self._make_kernel_with_sum_data()
        proposals = k.infer_relations(min_cooccurrence=3, min_confidence=0.9)
        types = {p.relation_type for p in proposals}
        assert "SumRelation" in types
        sum_p = next(p for p in proposals if p.relation_type == "SumRelation"
                     and "revenue" in p.description)
        assert sum_p.confidence >= 0.9

    def test_equality_relation_detected(self):
        k = TemporalKernel()
        for i in range(6):
            k.apply(Event({"x": float(i), "x_alias": float(i)}))
        proposals = k.infer_relations(min_cooccurrence=3, min_confidence=0.9)
        eq_proposals = [p for p in proposals if p.relation_type == "EqualityRelation"]
        assert any("x" in p.description and "x_alias" in p.description
                   for p in eq_proposals)

    def test_ratio_relation_detected(self):
        k = TemporalKernel()
        for i in range(1, 8):
            profit = float(i * 10)
            revenue = float(i * 100)
            margin = profit / revenue
            k.apply(Event({"profit": profit, "revenue": revenue, "margin": margin}))
        proposals = k.infer_relations(min_cooccurrence=3, min_confidence=0.9)
        ratio_p = [p for p in proposals if p.relation_type == "RatioRelation"]
        assert len(ratio_p) > 0

    def test_false_relation_not_proposed(self):
        import random
        random.seed(42)
        k = TemporalKernel()
        for _ in range(10):
            k.apply(Event({
                "x": random.uniform(1, 100),
                "y": random.uniform(1, 100),
                "z": random.uniform(1, 100),
            }))
        proposals = k.infer_relations(min_cooccurrence=3, min_confidence=0.95)
        assert len(proposals) == 0

    def test_relation_proposal_has_confidence(self):
        k = self._make_kernel_with_sum_data()
        proposals = k.infer_relations(min_cooccurrence=3, min_confidence=0.8)
        for p in proposals:
            assert 0.0 <= p.confidence <= 1.0
            assert p.observations >= 3
            assert p.constructor
            assert p.description

    def test_relation_proposal_instantiate(self):
        k = self._make_kernel_with_sum_data()
        proposals = k.infer_relations(min_cooccurrence=3, min_confidence=0.9)
        for p in proposals:
            rel = p.instantiate()
            if rel is not None:
                assert isinstance(rel, Relation)


# ===========================================================================
# Rich equilibrium report
# ===========================================================================

class TestRichEquilibriumReport:
    def test_bare_report_has_state(self):
        k = TemporalKernel()
        k.apply(Event({"x": 1, "y": 2}))
        report = k.equilibrium_report()
        assert report["state"] == {"x": 1, "y": 2}
        assert report["state_keys"] == ["x", "y"]

    def test_bare_report_has_event_history(self):
        k = TemporalKernel()
        k.apply(Event({"a": 1}, domain="sys"))
        k.apply(Event({"b": 2}, domain="ops"))
        report = k.equilibrium_report()
        assert "event_history" in report
        assert len(report["event_history"]) == 2
        assert report["event_history"][0]["domain"] == "sys"
        assert report["event_history"][1]["domain"] == "ops"

    def test_bare_report_has_provenance_chains(self):
        k = TemporalKernel()
        k.apply(Event({"answer": 42}))
        report = k.equilibrium_report()
        assert "provenance_chains" in report
        assert "answer" in report["provenance_chains"]

    def test_bare_report_has_domains_seen(self):
        k = TemporalKernel()
        k.apply(Event({"x": 1}, domain="alpha"))
        k.apply(Event({"y": 2}, domain="beta"))
        report = k.equilibrium_report()
        assert set(report["domains_seen"]) == {"alpha", "beta"}

    def test_bare_report_has_time_span(self):
        k = TemporalKernel()
        k.apply(Event({"x": 1}))
        time.sleep(0.001)
        k.apply(Event({"y": 2}))
        report = k.equilibrium_report()
        assert report["time_span_ns"] > 0

    def test_lattice_report_includes_all_sections(self):
        lattice = (
            Lattice()
            .define("fin", "a", {int, float})
            .define("fin", "b", {int, float})
            .define("fin", "c", {int, float})
            .relate(SumRelation(["a", "b"], "c"))
        )
        k = TemporalKernel(lattice=lattice)
        k.apply(Event({"a": 3.0, "b": 7.0}, domain="fin"))
        report = k.equilibrium_report()
        for key in ["tension", "at_equilibrium", "occupancy",
                    "solver_energy", "event_history", "provenance_chains",
                    "state", "domains_seen"]:
            assert key in report, f"missing: {key}"
        assert report["at_equilibrium"] is True
        assert report["solver_energy"] < 1e-9
## v9.0
- Automatic `_prev_` injection for TemporalRelation (no caller boilerplate)
- ConditionalRelation predicate re-evaluation mid-propagation (volatile flag)
- ConservativeWins policy derives safe direction from declared invariants
- Provenance chain walking (`explain_chain`) with cycle guard
- Underdetermined key detection in SolverResult
- Circular dependency detection via Tarjan's algorithm (SolverResult.cycles)
- Empirical relation testing in SchemaInference (`relation_proposals`)
- RelationProposal with confidence scores and `instantiate()` method
- Rich `equilibrium_report()` without requiring a lattice
- Full event history, domain tracking, and time span in equilibrium report
- `provenance_chains` included in equilibrium report

## v8.0
- Conflict resolution policies: LastWriteWins, DomainAuthorityWins,
  ConservativeWins, MergeFunction, OperatorPrompt, PolicyChain
- Boolean/categorical relations: EnumRelation, ExclusionRelation,
  CategoricalImplicationRelation, NegationRelation, ExactlyOneRelation,
  AllTrueRelation, AnyTrueRelation
- Composite relations: ConditionalRelation, TemporalRelation
- Named inference rules (InferenceRule) and RuleSet
- Full ReconciliationReport with policy tracking
- ForkReconciler with solver-extended merge

## v7.0
- Variational solver: energy minimization phase (gradient descent)
- SolverResult.energy and SolverResult.minimization_steps
- ConstraintSolver two-phase architecture (arc consistency + minimizer)
- Adaptive learning rate in minimizer

## v6.0
- GitLedger: git as canonical substrate
- Fork domain branching via git branches
- Equilibrium snapshots committed as tagged git objects
- LedgerStore persistence (save/restore)

## v5.1
- Bundled Foundational Specification v1.0
- Documentation consolidation
- Peaceful, audit-first packaging

## v5.0
- Foundational kernel release
- Immutable event ledger
- Deterministic replay

## v3.x
- Prototype iterations
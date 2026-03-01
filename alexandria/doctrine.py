"""
Alexandria — Doctrine Enforcement

Optional runtime checks to ensure philosophical alignment.
The doctrine lock defines the immutable constitutional properties
of the system. Any configuration that deviates raises RuntimeError.

See DOCTRINE.md for the full constitutional principles.
"""

DOCTRINE_LOCK = {
    "time_model": "linear_singular",
    "branching_allowed": False,
    "simulation_allowed": False,
    "state_is_primary": False,
    "non_determinism_allowed": False,
}


def assert_doctrine_alignment(config: dict):
    """
    Compare runtime configuration against doctrine lock.
    Raises RuntimeError on any violation.
    """
    for key, required in DOCTRINE_LOCK.items():
        if key in config and config[key] != required:
            raise RuntimeError(
                f"Doctrine violation: '{key}' must be {required!r}, "
                f"got {config[key]!r}"
            )


def print_doctrine_banner():
    print("""
    Alexandria Temporal Kernel
    Canonicalization Field — v9.0
    Linear Time · Invariant Bound · Domain Orthogonal
    """)

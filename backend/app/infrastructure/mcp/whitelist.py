"""Allowed Petri-Pilot MCP tool names for the runtime adapter."""

PETRI_PILOT_WHITELIST: frozenset[str] = frozenset(
    {
        "petri_validate",
        "petri_analyze",
        "petri_verify",
        "petri_invariants",
        "petri_simulate",
        "petri_conformance",
        "petri_diff",
        "petri_canonical",
    }
)

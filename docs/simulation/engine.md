# Simulation engine

See also `ram-engine.md` (detailed design) and `monte-carlo.md`.

## Contract

Input: `CompiledModel` + `ScenarioOverlay` + `SimulationConfiguration`
+ `seed`. Output: `SimulationRunResult`. The engine does not read the
database or call UI/HTTP.

## Properties

- Event-driven priority queue with deterministic tie-break.
- RNG via `numpy.random.SeedSequence` (no global random).
- Lazy diagnostics on the PF window.
- Time in minutes inside the engine (`UnitConverter` at boundaries).

## Golden checks

- P-101 exponential Ai ≈ MTBF/(MTBF+MTTR)
- PF detection prevents functional failure when `p_detect = 1`

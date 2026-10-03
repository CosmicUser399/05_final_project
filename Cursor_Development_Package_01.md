# AI RELIABILITY MODELLING

## Cursor Development Package v1.0

**Назначение:** непосредственная разработка приложения в Cursor IDE
**Тип системы:** browser-based industrial reliability modelling application
**Архитектура:** modular monolith
**Backend:** Python + FastAPI
**Frontend:** React + TypeScript + Vite
**Database:** SQLite → PostgreSQL-compatible architecture
**Simulation:** собственный event-driven RAM Monte Carlo Engine
**Formal Petri modelling:** Petri-Pilot через MCP adapter
**AI:** OpenAI через отдельный AI Orchestrator
**Reference data:** OREDA + ISO 14224 + user/manufacturer/historical data
**Deployment:** Docker Compose
**Target:** single-user MVP с возможностью дальнейшего перехода к multi-user

---

# 1. КЛЮЧЕВОЙ ПРИНЦИП РАЗРАБОТКИ

Система должна строиться не как:

```text
LLM
 ↓
Petri-Pilot
 ↓
Simulation
```

а как:

```text
                   ┌───────────────┐
                   │   Web UI      │
                   └───────┬───────┘
                           │
                   ┌───────▼───────┐
                   │   FastAPI     │
                   └───────┬───────┘
                           │
                 ┌─────────▼─────────┐
                 │ AI Orchestrator   │
                 └─────────┬─────────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
       Fabricate        OpenAI       Reference Data
            │              │              │
            └──────────────┼──────────────┘
                           ▼
                    Domain Model
                           │
                  Reliability Model
                           │
                ┌──────────┴──────────┐
                ▼                     ▼
          Petri Model             RAM Model
                │                     │
         Petri-Pilot             RAM Engine
                │                     │
                └──────────┬──────────┘
                           ▼
                    Simulation Results
                           │
                     AI Analyst
                           │
                        Web UI
```

**Критическое архитектурное правило:**

> Petri-Pilot не является заменой RAM Simulation Engine.

Petri-Pilot используется для формального представления, проверки и анализа Petri-модели.

RAM Engine отвечает за инженерное моделирование:

* отказов;
* PF interval;
* диагностики;
* ремонта;
* обслуживания;
* ресурсов;
* запасных частей;
* производственных потерь;
* Monte Carlo;
* RAM metrics.

---

# 2. SOURCE OF TRUTH

Единственным source of truth является domain database.

```text
Database
   ↓
Domain objects
   ↓
Reliability model
   ↓
Petri model
   ↓
Simulation
```

Не допускается:

```text
Excel → source of truth
LLM → source of truth
Petri-Pilot → source of truth
Generated JSON → source of truth
```

Excel является только import/export format.

LLM генерирует предложения.

Petri-Pilot является внешним formal modelling engine.

---

# 3. ОСНОВНЫЕ ARCHITECTURAL BOUNDARIES

## 3.1 Domain

Domain не должен зависеть от:

* FastAPI;
* React;
* OpenAI;
* Fabricate;
* MCP;
* Petri-Pilot;
* SQLAlchemy implementation details.

Domain содержит:

* entities;
* value objects;
* domain services;
* engineering calculations;
* validation rules.

---

## 3.2 Application

Application layer содержит use cases:

```text
CreateSystem
GenerateEquipment
GenerateFailureModes
GenerateMaintenance
GenerateReliabilityModel
GeneratePetriModel
ValidatePetriModel
CreateScenario
RunSimulation
CompareScenarios
AnalyzeSimulation
ImportExcel
ExportExcel
```

---

## 3.3 Infrastructure

Infrastructure содержит adapters:

```text
OpenAIAdapter
FabricateAdapter
PetriPilotAdapter
SQLiteRepository
ExcelRepository
OREDARepository
ISO14224Repository
```

Infrastructure может зависеть от Domain.

Domain не может зависеть от Infrastructure.

---

# 4. REPOSITORY STRUCTURE

Создать:

```text
ai-reliability-modelling/
│
├── .cursor/
│   └── rules/
│       ├── 001-architecture.mdc
│       ├── 002-domain.mdc
│       ├── 003-database.mdc
│       ├── 004-ai.mdc
│       ├── 005-mcp.mdc
│       ├── 006-simulation.mdc
│       ├── 007-units.mdc
│       ├── 008-testing.mdc
│       └── 009-security.mdc
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── application/
│   │   ├── domain/
│   │   │   ├── system/
│   │   │   ├── equipment/
│   │   │   ├── reliability/
│   │   │   ├── maintenance/
│   │   │   ├── diagnostics/
│   │   │   ├── production/
│   │   │   ├── resources/
│   │   │   ├── scenarios/
│   │   │   └── simulation/
│   │   │
│   │   ├── infrastructure/
│   │   │   ├── db/
│   │   │   ├── ai/
│   │   │   ├── mcp/
│   │   │   ├── reference_data/
│   │   │   └── files/
│   │   │
│   │   ├── simulation/
│   │   │   ├── engine/
│   │   │   ├── distributions/
│   │   │   ├── events/
│   │   │   ├── metrics/
│   │   │   └── random/
│   │   │
│   │   ├── config.py
│   │   └── main.py
│   │
│   ├── migrations/
│   └── tests/
│
├── frontend/
│   └── src/
│       ├── app/
│       ├── pages/
│       ├── features/
│       ├── components/
│       ├── api/
│       ├── hooks/
│       ├── types/
│       └── utils/
│
├── reference_data/
│   ├── oreda/
│   └── iso14224/
│
├── docs/
│   ├── architecture/
│   ├── api/
│   ├── domain/
│   ├── simulation/
│   └── decisions/
│
├── scripts/
│
├── docker/
├── docker-compose.yml
├── .env.example
├── Makefile
└── README.md
```

---

# 5. CURSOR DEVELOPMENT RULES

## Rule 1 — Domain first

Не добавлять бизнес-логику в:

* API routers;
* React components;
* MCP adapters;
* AI prompts.

---

## Rule 2 — LLM output is untrusted

Любой результат LLM:

```text
LLM
 ↓
Pydantic DTO
 ↓
Validation
 ↓
Normalization
 ↓
Domain object
 ↓
Persistence
```

Никогда:

```text
LLM → DB
```

---

## Rule 3 — Engineering parameters require provenance

Каждый AI-generated параметр должен иметь:

```text
source_type
source_document
source_reference
confidence
generated_by
generated_at
```

---

## Rule 4 — Explicit units

Нельзя:

```python
maintenance_interval = 30
```

Допустимо:

```python
MaintenanceInterval(
    value=30,
    unit=TimeUnit.DAYS
)
```

---

## Rule 5 — No implicit time conversion

Все simulation calculations должны использовать canonical internal unit:

```text
minutes
```

Conversion осуществляется только через единый UnitConverter.

---

## Rule 6 — Immutable model versions

Simulation всегда ссылается на конкретную версию:

```text
system_version_id
scenario_version_id
model_version_id
simulation_configuration_id
random_seed
```

---

## Rule 7 — Deterministic simulation

Одинаковые:

```text
model
scenario
configuration
seed
software version
```

должны давать воспроизводимый результат с допустимой численной погрешностью.

---

## Rule 8 — No arbitrary SQL from AI

AI не получает:

* raw SQL;
* DB credentials;
* произвольный database execution tool.

AI работает только через typed tools.

---

## Rule 9 — Long simulations are asynchronous

HTTP request не должен выполнять длительный Monte Carlo напрямую.

```text
POST /simulations
       ↓
job created
       ↓
worker
       ↓
simulation
       ↓
results
```

---

# 6. DOMAIN MODEL

Основные entities:

```text
System
SystemVersion

Equipment
EquipmentComponent
EquipmentConnection
EquipmentTaxonomy

FailureMode
FailureDistribution
PFInterval

MaintenanceTask
MaintenanceDistribution
MaintenanceEffect
ResourceRequirement
SparePartRequirement

DiagnosticTask

ProductionFunction
ProductionImpact

ReliabilityModel
PetriModel

Scenario
ScenarioVersion
ScenarioChange

SimulationConfiguration
SimulationRun

SystemMetrics
EquipmentMetrics

FailureEvent
MaintenanceEvent
DiagnosticEvent
ProductionLossEvent
ResourceConsumption
```

---

# 7. SYSTEM

```python
System:
    id
    name
    description
    created_at
    updated_at
    current_version_id
```

Example:

```text
name:
Установка производства полистирола - 100

code:
УПП-100
```

---

# 8. SYSTEM VERSION

```python
SystemVersion:
    id
    system_id
    version
    status
    created_at
    created_by
    source_version_id
```

Statuses:

```text
DRAFT
VALIDATED
RELEASED
ARCHIVED
```

Simulation может выполняться только над immutable version.

---

# 9. EQUIPMENT

```python
Equipment:
    id
    system_version_id
    parent_id

    tag
    name

    category
    equipment_class
    equipment_type

    manufacturer
    model
    serial_number

    commissioning_date

    quantity
    criticality

    standby_mode
    is_repairable

    description
```

---

# 10. TAXONOMY

Поддерживать несколько taxonomy одновременно.

```text
Taxonomy
    └── TaxonomyNode
```

Taxonomy types:

```text
BUSINESS
ISO_14224
COMPANY
API
IEC
CUSTOM
```

Пример:

```text
Rotating equipment
    └── Pump
        └── Centrifugal process pump
```

AI не должен придумывать ISO-14224 identifiers.

---

# 11. FAILURE MODE

```python
FailureMode:
    id
    equipment_id

    code
    name
    description

    failure_mechanism
    failure_cause
    failure_effect

    criticality
    detectable
    repairable

    failure_distribution_id
    pf_interval_id

    source_metadata
```

---

# 12. FAILURE DISTRIBUTION

Поддержать минимум:

```text
EXPONENTIAL
WEIBULL
LOGNORMAL
NORMAL
GAMMA
LOGLOGISTIC
EMPIRICAL
CONSTANT
```

Structure:

```python
FailureDistribution:
    type
    parameters
    unit
```

Examples:

```text
Exponential:
lambda

Weibull:
shape
scale

Lognormal:
mu
sigma
```

Distribution API:

```python
sample(rng) -> float
cdf(t) -> float
pdf(t) -> float
survival(t) -> float
mean() -> float
```

---

# 13. PF INTERVAL

PF Interval является обязательным параметром FailureMode, если failure mode поддерживает condition-based / detectable degradation.

```python
PFInterval:
    value: float
    unit: TimeUnit
```

Supported:

```text
MINUTES
HOURS
DAYS
MONTHS
YEARS
```

Семантика:

> Время между появлением первых обнаружимых признаков потенциального отказа и наступлением функционального отказа.

Не смешивать:

```text
PF Interval ≠ MTBF
PF Interval ≠ MTTR
PF Interval ≠ maintenance interval
PF Interval ≠ inspection interval
```

Canonical conversion:

```text
PFInterval → minutes
```

Simulation relation:

```text
T_pf = T_failure - PFInterval
```

При:

```text
T_pf < 0
```

потенциальное состояние не моделируется.

---

# 14. MAINTENANCE TASK

```python
MaintenanceTask:
    id
    equipment_id

    type
    name
    description

    trigger_type
    schedule

    maintenance_distribution
    maintenance_effect
    resource_requirements
    spare_part_requirements

    enabled
    source_metadata
```

Types:

```text
INSPECTION
DIAGNOSTIC
PREVENTIVE
CORRECTIVE
```

---

# 15. MAINTENANCE DISTRIBUTION

Maintenance duration моделируется распределением.

Например:

```text
Lognormal
Normal
Gamma
Constant
Empirical
```

Interface:

```python
sample(rng) -> duration_minutes
```

---

# 16. MAINTENANCE EFFECT

MaintenanceEffect должен явно определять влияние на FailureMode.

Пример:

```python
MaintenanceEffect:
    failure_mode_id
    effect_type
    restoration_factor
    probability
```

Effect types:

```text
NONE
RESTORE_AS_NEW
RESTORE_AS_OLD
PARTIAL_RESTORATION
REDUCE_FAILURE_RATE
RESET_DEGRADATION
```

---

# 17. RESOURCE REQUIREMENT

```python
ResourceRequirement:
    resource_id
    quantity
    required_duration
    priority
```

Resources:

```text
technician
mechanic
electrician
instrumentation
crane
special_tool
workshop
```

---

# 18. SPARE PART REQUIREMENT

```python
SparePartRequirement:
    spare_part_id
    quantity
    probability
    replacement_time
```

SparePart:

```text
code
name
unit_cost
stock_quantity
lead_time_distribution
```

---

# 19. DIAGNOSTICS

Diagnostic task:

```python
DiagnosticTask:
    id
    equipment_id
    failure_mode_id

    interval
    detection_probability

    false_positive_probability
    false_negative_probability

    duration_distribution
    enabled
```

PF interaction:

```text
NORMAL
   ↓
POTENTIAL FAILURE
   ↓
DIAGNOSTIC
   ↓
DETECTED
   ↓
PLANNED MAINTENANCE
```

If detection fails:

```text
POTENTIAL FAILURE
   ↓
FUNCTIONAL FAILURE
```

---

# 20. EQUIPMENT STATE MACHINE

Minimum states:

```text
UP
POTENTIAL_FAILURE
FAILED
DIAGNOSIS
WAITING_FOR_RESOURCE
WAITING_FOR_SPARE
MAINTENANCE
RESTORING
STANDBY
```

State transitions должны быть explicit.

---

# 21. EQUIPMENT CONNECTION

```python
EquipmentConnection:
    from_equipment_id
    to_equipment_id

    connection_type

    capacity
    direction

    dependency_type
```

Types:

```text
PROCESS
ELECTRICAL
CONTROL
UTILITY
MATERIAL
INSTRUMENTATION
DEPENDENCY
```

---

# 22. PRODUCTION MODEL

```python
ProductionFunction:
    id
    system_version_id

    nominal_rate
    unit

    operating_dependencies
```

ProductionImpact:

```python
ProductionImpact:
    equipment_id
    failure_mode_id

    impact_type
    loss_fraction
    reduced_rate
```

Types:

```text
FULL_LOSS
PARTIAL_LOSS
THROUGHPUT_REDUCTION
QUALITY_LOSS
NO_PRODUCTION_LOSS
```

---

# 23. REDUNDANCY

Support:

```text
SERIES
PARALLEL
K_OF_N
STANDBY
```

Do not hard-code redundancy logic into equipment.

Create:

```python
ReliabilityStructure
ReliabilityStructureMember
```

---

# 24. RELIABILITY MODEL

ReliabilityModel содержит:

```text
model_id
system_version_id
model_version
generation_status
validation_status
generated_at
```

Model should include:

* equipment;
* failure modes;
* maintenance;
* diagnostics;
* dependencies;
* production;
* redundancy;
* resources;
* spares.

---

# 25. PETRI MODEL

Petri model is a derived artifact.

```python
PetriModel:
    id
    reliability_model_id

    definition_json
    version
    validation_status

    petri_pilot_version
    generated_at
```

Every Petri element should have mapping:

```text
source_entity_type
source_entity_id
```

Example:

```text
Place:
EquipmentState
UPP100-P-101
UP

Transition:
FailureMode
FM-P101-001
```

---

# 26. PETRI-PILOT ADAPTER

Never call Petri-Pilot directly from domain.

Interface:

```python
class PetriPilotPort:

    async def validate(model):
        ...

    async def analyze(model):
        ...

    async def verify(model):
        ...

    async def simulate(model, config):
        ...

    async def codegen(model):
        ...
```

Implementation:

```text
PetriPilotMCPAdapter
```

MCP transport details must remain inside adapter.

---

# 27. RAM ENGINE

Create:

```text
backend/app/simulation/
```

with:

```text
engine/
events/
distributions/
metrics/
random/
```

Core API:

```python
class SimulationEngine:

    def run(
        model,
        scenario,
        configuration,
        seed
    ) -> SimulationRunResult:
        ...
```

---

# 28. EVENT-DRIVEN SIMULATION

Do not use fixed timestep simulation for the core engine.

Use priority queue:

```text
event_queue
```

Events:

```text
FAILURE
POTENTIAL_FAILURE
DIAGNOSTIC
DETECTION
PM_START
PM_COMPLETE
CM_START
CM_COMPLETE
SPARE_REQUEST
SPARE_AVAILABLE
RESOURCE_BUSY
RESOURCE_AVAILABLE
PRODUCTION_CHANGE
```

Event:

```python
SimulationEvent:
    time
    type
    equipment_id
    failure_mode_id
    payload
```

---

# 29. RANDOM NUMBER GENERATION

Use NumPy Generator.

Example:

```python
rng = numpy.random.default_rng(seed)
```

For Monte Carlo:

```text
master_seed
    ↓
run-specific seed
    ↓
independent RNG
```

Recommended:

```python
seed_i = hash((master_seed, run_id))
```

Do not use global random state.

---

# 30. FAILURE GENERATION

Each failure mode has distribution.

For each simulation run:

```text
sample failure time
```

For repairable equipment:

```text
failure
 ↓
repair
 ↓
new operating period
 ↓
failure
```

Competing failure modes must be supported.

For competing risks:

```text
T = min(T1, T2, ..., Tn)
```

The winning failure mode determines the event.

---

# 31. PF EVENT GENERATION

If:

```text
failure_time = T
PF_interval = P
```

then:

```text
potential_failure_time = T - P
```

Generate:

```text
POTENTIAL_FAILURE
```

before:

```text
FAILURE
```

if:

```text
P > 0
and
T > P
```

---

# 32. DIAGNOSTIC LOGIC

At inspection time:

```text
if equipment is in POTENTIAL_FAILURE:
    detect according to detection_probability
```

If detected:

```text
DETECTION
    ↓
planned maintenance
```

If not detected:

```text
continue degradation
```

until:

```text
FUNCTIONAL FAILURE
```

False positives:

```text
NORMAL
 ↓
false detection
 ↓
inspection / maintenance
```

must be separately logged.

---

# 33. MAINTENANCE LOGIC

Corrective:

```text
FAILED
 ↓
CM_START
 ↓
WAITING_RESOURCE
 ↓
WAITING_SPARE
 ↓
MAINTENANCE
 ↓
RESTORING
 ↓
UP
```

Preventive:

```text
UP
 ↓
PM_START
 ↓
MAINTENANCE
 ↓
UP
```

---

# 34. RESOURCE LOGIC

Resources have:

```text
capacity
availability
current utilization
```

If resource unavailable:

```text
WAITING_FOR_RESOURCE
```

Simulation must capture waiting time.

This contributes to:

```text
MDT
Operational Availability
```

---

# 35. SPARE LOGIC

If spare unavailable:

```text
WAITING_FOR_SPARE
```

lead time sampled from distribution.

Consumption recorded:

```python
ResourceConsumption:
    simulation_run_id
    spare_part_id
    quantity
    cost
    timestamp
```

---

# 36. PRODUCTION LOSS

For every production-affecting state:

```text
production_rate(t)
```

Production loss:

```text
loss =
nominal_rate - actual_rate
```

Total:

```text
ProductionLoss =
Σ(loss_rate × duration)
```

Store both:

```text
absolute production loss
production loss %
```

---

# 37. RAM METRICS

## Reliability

```text
R(t) = P(T_failure > t)
```

Monte Carlo:

```text
surviving_runs / total_runs
```

---

## MTBF

```text
MTBF =
total operating time /
number of functional failures
```

---

## MTTR

```text
MTTR =
total corrective repair time /
number of corrective repairs
```

---

## Inherent / Technical Availability

```text
Ai =
MTBF /
(MTBF + MTTR)
```

---

## MTBM

```text
MTBM =
total operating time /
number of maintenance events
```

---

## Operational Availability

```text
Ao =
MTBM /
(MTBM + MDT)
```

---

## Maintainability

```text
M(t) =
P(Trepair <= t)
```

---

## Production Availability

```text
actual production /
nominal production
```

---

# 38. CONFIDENCE INTERVALS

For Monte Carlo outputs calculate:

```text
mean
median
P5
P50
P95
confidence interval
```

For proportions such as availability/reliability, use a statistically appropriate confidence interval implementation rather than blindly applying normal approximation at all sample sizes.

---

# 39. SIMULATION CONFIGURATION

```python
SimulationConfiguration:
    horizon
    horizon_unit

    number_of_runs

    random_seed

    warmup_period

    confidence_level

    collect_event_log
    collect_equipment_metrics
    collect_resource_consumption
    collect_production_loss

    parallel_runs
```

---

# 40. SIMULATION RUN

```text
QUEUED
VALIDATING
RUNNING
COMPLETED
FAILED
CANCELLED
```

SimulationRun:

```text
id
model_version_id
scenario_version_id
configuration_id

started_at
completed_at

status
progress

software_version
random_seed
```

---

# 41. SIMULATION RESULTS

SystemMetrics:

```text
reliability
availability
maintainability

MTBF
MTTR
MTBM
MDT

downtime
production_loss
production_availability

failure_count
maintenance_count
diagnostic_count
```

EquipmentMetrics:

```text
equipment_id

failure_count
downtime

MTBF
MTTR

availability

PM_count
CM_count
diagnostic_count

production_loss

spare_consumption
```

---

# 42. EVENT LOG

Event log must be queryable.

```python
FailureEvent
MaintenanceEvent
DiagnosticEvent
ProductionLossEvent
```

Common fields:

```text
simulation_run_id
timestamp
equipment_id
event_type
failure_mode_id
duration
metadata
```

Do not store the entire event history only inside one JSON field.

---

# 43. SCENARIOS

Baseline model is immutable.

Scenario contains changes.

Example:

```text
Scenario:
Baseline

Scenario:
Vibration monitoring every 30 days

Scenario:
Vibration monitoring every 14 days
```

Changes:

```text
CHANGE_DIAGNOSTIC_INTERVAL
CHANGE_DETECTION_PROBABILITY
CHANGE_PM_INTERVAL
CHANGE_MAINTENANCE_DISTRIBUTION
CHANGE_RESOURCE
CHANGE_SPARE_STOCK
CHANGE_FAILURE_PARAMETER
ENABLE_TASK
DISABLE_TASK
```

---

# 44. AI ORCHESTRATOR

AI must use typed tools.

Recommended tools:

```text
get_system
get_equipment
get_failure_modes
get_maintenance_tasks
get_reference_data

create_equipment
create_failure_mode
create_maintenance_task

validate_model

generate_petri_model
validate_petri_model

run_simulation
get_simulation_results

compare_scenarios
```

AI should not directly manipulate arbitrary DB records.

---

# 45. AI SYSTEM GENERATION PIPELINE

User:

```text
Типовая установка производства полистирола из стирола,
мощность 100 тыс. тонн в год
```

Pipeline:

```text
User description
       ↓
AI extraction
       ↓
System proposal
       ↓
Equipment proposal
       ↓
Failure mode proposal
       ↓
Maintenance proposal
       ↓
Reference-data enrichment
       ↓
Validation
       ↓
User review
       ↓
Persist
```

Every generated engineering parameter receives provenance.

---

# 46. AI GENERATION DTO

Example:

```python
GeneratedEquipment:
    tag
    name
    category
    equipment_class
    equipment_type

    confidence
    source_references
    assumptions
```

AI must not return executable SQL.

---

# 47. VALIDATION LEVELS

## Level 1 — Syntax

JSON/schema valid.

## Level 2 — Domain

Required fields and relationships valid.

## Level 3 — Engineering

Examples:

```text
PF interval >= 0
probability in [0,1]
scale > 0
shape > 0
duration > 0
```

## Level 4 — Model

Check:

* disconnected equipment;
* invalid dependencies;
* impossible maintenance transitions;
* missing failure distributions;
* missing production impact;
* impossible resource requirements.

## Level 5 — Petri

Use Petri-Pilot validation.

---

# 48. REFERENCE DATA

Create adapters:

```text
OREDARepository
ISO14224Repository
```

Do not hard-code OREDA values directly into business logic.

Every reference parameter:

```text
value
unit
source_type
source_document
source_reference
confidence
```

Source types:

```text
OREDA
ISO_14224
USER_DEFINED
AI_ESTIMATE
ENGINEERING_ASSUMPTION
HISTORICAL_DATA
MANUFACTURER_DATA
```

---

# 49. DATABASE

Use SQLAlchemy 2.

Alembic migrations.

SQLite initially.

Do not use SQLite-specific domain logic.

Use UUID identifiers.

Recommended:

```text
SQLite
    ↓
SQLAlchemy
    ↓
PostgreSQL
```

should require minimal application changes.

---

# 50. API

Base:

```text
/api/v1
```

Systems:

```http
GET    /systems
POST   /systems
GET    /systems/{id}
PATCH  /systems/{id}
DELETE /systems/{id}
```

Versions:

```http
GET  /systems/{id}/versions
POST /systems/{id}/versions
GET  /versions/{id}
```

Equipment:

```http
GET    /versions/{id}/equipment
POST   /versions/{id}/equipment
GET    /equipment/{id}
PATCH  /equipment/{id}
DELETE /equipment/{id}
```

Failure modes:

```http
GET   /equipment/{id}/failure-modes
POST  /equipment/{id}/failure-modes
PATCH /failure-modes/{id}
```

Maintenance:

```http
GET   /equipment/{id}/maintenance
POST  /equipment/{id}/maintenance
PATCH /maintenance/{id}
```

Petri:

```http
POST /versions/{id}/petri/generate
POST /petri/{id}/validate
POST /petri/{id}/analyze
```

Simulation:

```http
POST /simulations
GET  /simulations/{id}
GET  /simulations/{id}/status
GET  /simulations/{id}/results
GET  /simulations/{id}/events
```

Scenarios:

```http
GET  /versions/{id}/scenarios
POST /versions/{id}/scenarios
POST /scenarios/{id}/simulate
GET  /scenarios/{id}/compare
```

AI:

```http
POST /ai/generate-system
POST /ai/generate-equipment
POST /ai/generate-failure-modes
POST /ai/generate-maintenance
POST /ai/chat
```

---

# 51. API RULE

Routers должны быть тонкими.

Нельзя:

```python
@router.post("/simulate")
def simulate():
    # 500 lines of simulation
```

Допустимо:

```python
@router.post("/simulate")
def simulate(
    command: RunSimulationCommand
):
    return simulation_service.execute(command)
```

---

# 52. FRONTEND

React + TypeScript + Vite.

Recommended:

```text
TanStack Query
React Router
MUI or Ant Design
React Flow
ECharts
```

---

# 53. FRONTEND PAGES

```text
Systems
System Overview
Database
Equipment Schema
Reliability Model
Petri Model
Scenarios
Simulation
Results
AI Analysis
```

---

# 54. DATABASE UI

Tables:

```text
Equipment
Failure Modes
Maintenance
Resources
Spare Parts
Connections
Production
```

Required:

```text
search
filter
sort
pagination
inline edit
bulk edit
import
export
```

---

# 55. EQUIPMENT GRAPH

Use React Flow.

Nodes:

```text
equipment
```

Edges:

```text
process
electrical
control
utility
dependency
```

Actions:

```text
select
zoom
pan
filter
highlight
show failure state
show production impact
```

---

# 56. PETRI UI

Display:

```text
places
transitions
arcs
tokens
```

Allow:

```text
zoom
pan
collapse
expand
highlight
```

Clicking Petri element should identify source entity.

Example:

```text
Petri Transition
     ↓
FailureMode
     ↓
Equipment
```

---

# 57. SIMULATION UI

Configuration:

```text
Horizon
Number of runs
Random seed
Warm-up
Confidence level
```

Progress:

```text
queued
validating
running
completed
failed
cancelled
```

Use:

```text
SSE
```

or WebSocket.

Prefer SSE for MVP unless bidirectional communication is actually needed.

---

# 58. RESULTS UI

Dashboard:

```text
Reliability
Availability
Maintainability
MTBF
MTTR
MTBM
MDT
Downtime
Production Loss
Production Availability
```

Charts:

```text
Reliability curve
Availability distribution
Downtime distribution
Failure Pareto
Production loss Pareto
Maintenance workload
Spare consumption
```

---

# 59. AI ANALYST

After simulation user can ask:

```text
Какие единицы оборудования дали наибольший вклад
в потерю производства?
```

or:

```text
Какие отказы наиболее часто приводили к остановке?
```

AI must answer from stored simulation results.

Pipeline:

```text
User question
 ↓
intent classification
 ↓
typed data queries
 ↓
calculation if necessary
 ↓
AI synthesis
 ↓
answer + references to simulation/model
```

Do not allow AI to invent results.

---

# 60. EXCEL

Excel import/export is a boundary adapter.

Workbook sheets:

```text
Systems
Equipment
Components
Connections
FailureModes
FailureDistributions
PFIntervals
Maintenance
MaintenanceEffects
Diagnostics
Resources
SpareParts
Production
```

Import:

```text
Excel
 ↓
DTO
 ↓
Validation
 ↓
Domain
 ↓
DB
```

Export:

```text
DB
 ↓
Domain
 ↓
Excel
```

---

# 61. OBSERVABILITY

Use structured logging.

Every simulation should log:

```text
system_id
system_version_id
model_version_id
scenario_id
simulation_id
seed
software_version
```

---

# 62. ERROR MODEL

Typed errors:

```text
ValidationError
DomainError
ModelGenerationError
PetriValidationError
SimulationError
ReferenceDataError
AIProviderError
ExternalServiceError
```

API maps them to predictable HTTP responses.

---

# 63. SECURITY

MVP:

```text
single-user
```

Nevertheless:

* secrets only in environment variables;
* no API keys in frontend;
* no arbitrary SQL;
* no arbitrary shell commands from AI;
* validate uploaded files;
* validate all AI-generated data;
* limit simulation parameters;
* protect admin/debug endpoints.

---

# 64. TESTING STRATEGY

## Unit tests

Must cover:

```text
time units
distributions
PF interval
failure generation
competing risks
diagnostics
maintenance
resources
spares
production loss
metrics
```

---

## Mathematical tests

Test:

```text
Exponential reliability
Weibull sampling
Ai
Ao
MTBF
MTTR
MTBM
MDT
Maintainability
Production loss
PF timing
```

---

## Integration tests

```text
API → DB
AI → DTO validation
DTO → Domain
Domain → Petri
Petri → Petri-Pilot adapter
Simulation → DB
Scenario → Simulation
```

---

## Golden tests

Fixed:

```text
model
scenario
configuration
seed
```

must produce stable metrics within predefined tolerance.

---

# 65. MINIMUM GOLDEN TEST

Create simple model:

```text
Pump P-101
```

Failure:

```text
Exponential
MTBF = 1000 h
```

Repair:

```text
Constant
MTTR = 10 h
```

Expected:

```text
Ai ≈ 1000 / 1010
```

Simulation should converge toward theoretical result as number of runs increases.

---

# 66. PF GOLDEN TEST

Model:

```text
Failure time = 1000 h
PF interval = 100 h
```

Expected:

```text
Potential failure = 900 h
Functional failure = 1000 h
```

Diagnostic at:

```text
950 h
```

with:

```text
detection_probability = 1
```

must detect potential failure.

Corrective failure should not occur if maintenance completes before 1000 h.

---

# 67. FIRST MVP DATASET

Create simplified УПП-100 dataset.

At minimum:

```text
Feed pump
Reactor
Agitator
Heat exchanger
Compressor
Cooling system
Control valve
Storage tank
Electrical motor
Instrumentation
```

For each:

* taxonomy;
* connections;
* failure modes;
* distributions;
* PF interval where applicable;
* maintenance;
* production impact.

Dataset is for software testing, not engineering certification.

---

# 68. DEVELOPMENT PHASES

# Phase 0 — Repository Bootstrap

Tasks:

```text
create repository
create backend
create frontend
create Docker Compose
configure environment
configure linting
configure formatting
configure pytest
configure frontend tests
create README
create Cursor rules
```

Acceptance:

```text
docker compose up
backend available
frontend available
health endpoint works
```

---

# Phase 1 — Domain Foundation

Implement:

```text
System
SystemVersion
Equipment
EquipmentComponent
EquipmentConnection
Taxonomy
FailureMode
FailureDistribution
PFInterval
MaintenanceTask
MaintenanceDistribution
MaintenanceEffect
ResourceRequirement
SparePartRequirement
```

Acceptance:

```text
CRUD
validation
unit conversion
provenance
tests
```

---

# Phase 2 — Database + API

Implement:

```text
SQLAlchemy models
Alembic
repositories
services
REST endpoints
OpenAPI
```

Acceptance:

```text
create system
create version
create equipment
create failure mode
create maintenance task
retrieve complete model
```

---

# Phase 3 — AI Generation

Implement:

```text
OpenAI adapter
AI orchestrator
typed schemas
generation pipeline
validation
provenance
```

Acceptance:

User provides:

```text
system description
```

and receives editable:

```text
equipment list
```

without direct DB write from LLM.

---

# Phase 4 — Equipment Graph

Implement:

```text
connections API
React Flow
graph editing
filters
entity mapping
```

Acceptance:

Topology can be viewed and edited.

---

# Phase 5 — Reliability Model

Implement:

```text
ReliabilityModel
model validation
model generation
```

Acceptance:

Complete equipment database can be transformed into a validated reliability model.

---

# Phase 6 — Petri Model

Implement:

```text
PetriModel
Petri generator
PetriPilotAdapter
MCP integration
validation
analysis
```

Acceptance:

System model generates Petri model and Petri-Pilot validates it.

---

# Phase 7 — RAM Engine

Implement:

```text
event queue
RNG
failure generation
repair
maintenance
PF interval
diagnostics
resources
spares
production
```

Acceptance:

Simple repairable system can be simulated.

---

# Phase 8 — Monte Carlo

Implement:

```text
multiple runs
parallel runs
confidence intervals
aggregation
event logs
```

Acceptance:

Simulation produces deterministic results for fixed seed and statistically sensible convergence.

---

# Phase 9 — Metrics

Implement:

```text
Reliability
Availability
Maintainability
MTBF
MTTR
MTBM
MDT
Production Availability
Production Loss
```

Acceptance:

All golden tests pass.

---

# Phase 10 — Scenarios

Implement:

```text
scenario
scenario version
scenario changes
comparison
```

Acceptance:

Two maintenance strategies can be simulated without modifying baseline model.

---

# Phase 11 — Results UI

Implement:

```text
dashboard
charts
equipment metrics
event explorer
```

Acceptance:

Simulation results can be inspected without querying DB manually.

---

# Phase 12 — AI Analyst

Implement:

```text
simulation query tools
AI analysis
result explanation
```

Acceptance:

AI answers only from simulation/model data.

---

# Phase 13 — OREDA / ISO

Implement:

```text
reference data ingestion
search
mapping
provenance
```

Acceptance:

Generated equipment can be linked to reference data.

---

# Phase 14 — Excel

Implement:

```text
import
export
validation
error report
```

Acceptance:

Round-trip:

```text
DB → Excel → DB
```

preserves supported data.

---

# 69. CURSOR TASK FORMAT

Каждая задача Cursor должна иметь:

```text
ID
Title
Objective
Files
Dependencies
Implementation
Tests
Acceptance Criteria
Non-Goals
```

Example:

```text
TASK: SIM-001

Title:
Implement TimeUnit and UnitConverter

Objective:
Provide canonical conversion of time values to minutes.

Files:
backend/app/domain/shared/time.py
backend/tests/domain/shared/test_time.py

Dependencies:
None

Implementation:
- TimeUnit enum
- TimeValue value object
- conversion to minutes
- conversion between units
- reject negative values where domain prohibits them

Tests:
- minutes → hours
- hours → days
- days → months
- years → days
- invalid values

Acceptance:
All tests pass.
No business logic outside unit module.

Non-Goals:
No simulation implementation.
```

---

# 70. TASK DEPENDENCY GRAPH

Основная последовательность:

```text
BOOT
  ↓
DOMAIN
  ↓
DATABASE
  ↓
API
  ↓
AI GENERATION
  ↓
RELIABILITY MODEL
  ↓
PETRI MODEL
  ↓
RAM ENGINE
  ↓
MONTE CARLO
  ↓
METRICS
  ↓
SCENARIOS
  ↓
RESULTS UI
  ↓
AI ANALYST
  ↓
REFERENCE DATA
  ↓
EXCEL
```

Но:

```text
Equipment Graph
```

может разрабатываться параллельно после API.

---

# 71. CRITICAL PATH

Cursor Planner должен считать critical path:

```text
Domain
→ Persistence
→ Reliability Model
→ RAM Engine
→ Monte Carlo
→ Metrics
→ Results
```

Petri-Pilot integration не должна блокировать разработку RAM Engine.

Это важное архитектурное решение.

---

# 72. PARALLEL DEVELOPMENT STREAMS

После Phase 2 можно вести параллельно:

```text
STREAM A
Domain / Simulation

STREAM B
Petri-Pilot integration

STREAM C
Frontend

STREAM D
AI Orchestrator

STREAM E
Reference data

STREAM F
Testing
```

---

# 73. DEFINITION OF DONE

Task считается выполненной только если:

```text
implementation exists
tests exist
tests pass
typing passes
lint passes
API contract updated
documentation updated where needed
no architecture rule violated
```

Для domain/simulation tasks обязательно:

```text
unit tests
```

Для API:

```text
integration test
```

Для simulation:

```text
deterministic test
```

---

# 74. RELEASE GATES

## Gate 1

```text
Domain stable
DB migrations stable
CRUD works
```

## Gate 2

```text
Reliability model generated
Petri validated
```

## Gate 3

```text
RAM simulation works
```

## Gate 4

```text
Monte Carlo validated
```

## Gate 5

```text
Results UI works
```

## Gate 6

```text
AI analyst works
```

---

# 75. NON-GOALS FOR MVP

Не реализовывать сразу:

```text
multi-user collaboration
RBAC
cloud-native microservices
Kubernetes
real-time SCADA
CMMS integration
automatic maintenance optimization
Bayesian calibration
digital twin synchronization
large-scale distributed Monte Carlo
```

Архитектура должна оставить возможность для них позже.

---

# 76. PERFORMANCE TARGETS FOR MVP

Цели, а не жёсткие ограничения:

```text
CRUD response:
< 500 ms typical

Model generation:
seconds

Petri validation:
seconds

Small simulation:
seconds

10k Monte Carlo runs:
acceptable interactive/background execution

100k+ runs:
background job
```

Не оптимизировать premature.

Сначала correctness.

---

# 77. SIMULATION CORRECTNESS PRIORITY

При конфликте:

```text
Correctness
    >
Reproducibility
    >
Traceability
    >
Performance
    >
UI convenience
```

---

# 78. ENGINEERING DATA TRACEABILITY

Для любого параметра пользователь должен иметь возможность увидеть:

```text
Parameter:
MTBF

Value:
1250 h

Source:
OREDA

Reference:
...

Confidence:
...

Generated/entered:
...

Last modified:
...
```

Для AI estimate:

```text
AI_ESTIMATE
```

должен быть визуально отличим от:

```text
OREDA
MANUFACTURER_DATA
USER_DEFINED
HISTORICAL_DATA
```

---

# 79. AI MUST EXPOSE ASSUMPTIONS

Если данных недостаточно:

```text
Unknown
```

или:

```text
Engineering assumption
```

а не искусственно точное значение.

Example:

```text
PF Interval:
30 days

Source:
ENGINEERING_ASSUMPTION

Confidence:
LOW
```

---

# 80. VALIDATION OF AI-GENERATED ENGINEERING DATA

Example:

```text
failure_probability = 1.7
```

→ reject.

```text
PF interval = -30 days
```

→ reject.

```text
Weibull shape = 0
```

→ reject.

```text
maintenance duration = 0
```

→ reject unless explicitly allowed.

---

# 81. AI CHAT TOOL BOUNDARY

AI chat should have access only to tools such as:

```text
system.get
equipment.search
failure_mode.search
maintenance.search
simulation.get_metrics
simulation.get_events
simulation.compare
scenario.get
reference.search
```

No unrestricted:

```text
sql.execute
shell.execute
filesystem.write
```

---

# 82. MODEL VERSION HASH

Create deterministic model fingerprint:

```text
model_hash =
SHA256(canonical_serialized_model)
```

Use it for:

```text
reproducibility
cache
comparison
audit
```

---

# 83. SIMULATION FINGERPRINT

Create:

```text
simulation_fingerprint =
SHA256(
    model_hash +
    scenario_hash +
    configuration_hash +
    seed +
    software_version
)
```

This makes runs traceable.

---

# 84. CACHING

Future optimization:

```text
same fingerprint
    ↓
existing result
```

MVP may disable result reuse but should calculate fingerprint from the beginning.

---

# 85. API IDEMPOTENCY

Simulation creation should support idempotency:

```text
Idempotency-Key
```

This prevents accidental duplicate long simulations.

---

# 86. BACKGROUND WORKER

MVP options:

```text
FastAPI
+
Redis
+
RQ/Celery
```

or a simple local process worker.

Architecture should isolate:

```python
SimulationJobRunner
```

so the queue technology can change.

---

# 87. PETRI-PILOT FAILURE HANDLING

External Petri-Pilot failure must not crash the whole application.

Adapter returns:

```text
success
failure
timeout
validation_error
external_error
```

Store external request/response metadata where useful, but do not store secrets.

---

# 88. EXTERNAL SERVICE CONTRACTS

Create interfaces:

```python
AIProvider
FabricateProvider
PetriPilotProvider
```

Application depends on interfaces.

Implementations live in infrastructure.

This allows mock implementations for tests.

---

# 89. MOCK PROVIDERS

Tests must be able to run without:

```text
OpenAI
Fabricate
Petri-Pilot
```

Provide:

```text
MockAIProvider
MockFabricateProvider
MockPetriPilotProvider
```

---

# 90. LOCAL DEVELOPMENT

Required:

```bash
docker compose up
```

Should start:

```text
backend
frontend
database
worker
```

where applicable.

Health:

```http
GET /health
```

Readiness:

```http
GET /ready
```

---

# 91. ENVIRONMENT

`.env.example`:

```text
APP_ENV=development

DATABASE_URL=sqlite:///./data/app.db

OPENAI_API_KEY=

FABRICATE_API_URL=

PETRI_PILOT_MCP_URL=

REDIS_URL=

LOG_LEVEL=INFO
```

Never commit `.env`.

---

# 92. DOCUMENTATION

Maintain:

```text
docs/
├── architecture/
│   ├── overview.md
│   ├── boundaries.md
│   └── decisions.md
│
├── domain/
│   ├── entities.md
│   ├── states.md
│   └── units.md
│
├── simulation/
│   ├── engine.md
│   ├── events.md
│   └── metrics.md
│
└── api/
    └── overview.md
```

---

# 93. ARCHITECTURE DECISION RECORDS

Create ADRs for:

```text
ADR-001 Modular monolith
ADR-002 SQLite first / PostgreSQL compatible
ADR-003 Petri-Pilot + own RAM Engine
ADR-004 Event-driven simulation
ADR-005 Domain DB as source of truth
ADR-006 LLM as orchestrator, not authority
ADR-007 Immutable model versions
ADR-008 Explicit units
ADR-009 Event log design
ADR-010 Scenario architecture
```

---

# 94. FIRST CURSOR AGENT PROMPT

Use the following prompt for the initial Cursor Planner:

```text
You are the lead software architect for the AI Reliability Modelling project.

Read:
1. the project Technical Specification;
2. this Cursor Development Package;
3. all files under .cursor/rules/.

Your first task is NOT to write implementation code.

Create a concrete implementation plan.

Requirements:

- Preserve the modular-monolith architecture.
- Preserve the separation:
    Domain
    Application
    Infrastructure
    Simulation
    API
    Frontend.
- Treat the domain database as the source of truth.
- Treat LLM output as untrusted proposal data.
- Keep Petri-Pilot behind an adapter.
- Do not use Petri-Pilot as a replacement for the RAM Simulation Engine.
- Build a dedicated event-driven RAM Monte Carlo Engine.
- Preserve PF Interval as a first-class FailureMode property.
- Preserve explicit units.
- Preserve immutable model/scenario versions.
- Preserve provenance for engineering parameters.
- Preserve deterministic simulation seeds.
- Do not introduce microservices.
- Do not over-engineer MVP.

Produce:

1. repository implementation plan;
2. dependency graph;
3. ordered implementation phases;
4. atomic Cursor tasks;
5. task dependencies;
6. files to create/change;
7. database migration plan;
8. API contract plan;
9. domain model plan;
10. simulation-engine plan;
11. Petri-Pilot integration plan;
12. frontend plan;
13. test plan;
14. acceptance criteria;
15. risks and mitigation.

Every task must contain:

ID
Title
Objective
Dependencies
Files
Implementation notes
Tests
Acceptance criteria
Non-goals

Do not implement anything until the plan is internally consistent.
```

---

# 95. SECOND CURSOR AGENT PROMPT — DOMAIN

```text
Implement only the Domain Foundation phase.

Do not implement:
- FastAPI endpoints;
- React;
- OpenAI;
- Fabricate;
- Petri-Pilot;
- Monte Carlo engine.

Implement:

System
SystemVersion
Equipment
EquipmentComponent
EquipmentConnection
Taxonomy
TaxonomyNode
FailureMode
FailureDistribution
PFInterval
MaintenanceTask
MaintenanceDistribution
MaintenanceEffect
ResourceRequirement
SparePartRequirement
DiagnosticTask
ProductionFunction
ProductionImpact

Requirements:

- domain must not depend on infrastructure;
- explicit units;
- PF Interval is first-class;
- engineering parameters have provenance;
- all invalid engineering values must be rejected;
- use typed value objects;
- provide comprehensive unit tests.

Before coding, inspect the existing repository and avoid duplicating existing abstractions.

After implementation run all relevant tests and report:
- files changed;
- tests added;
- tests passed;
- architectural assumptions.
```

---

# 96. THIRD CURSOR AGENT PROMPT — RAM ENGINE

```text
Implement the RAM Simulation Engine.

Architecture constraints:

- event-driven;
- no fixed timestep core loop;
- deterministic RNG;
- independent RNG per Monte Carlo run;
- explicit time units;
- domain-independent simulation kernel where practical;
- domain-specific reliability behavior in appropriate services.

Implement:

EventQueue
SimulationClock
RandomProvider
FailureGenerator
CompetingRiskModel
PFIntervalScheduler
DiagnosticEngine
MaintenanceEngine
ResourceManager
SparePartManager
ProductionImpactEngine
SimulationEngine
MetricsCollector

Events:

FAILURE
POTENTIAL_FAILURE
DIAGNOSTIC
DETECTION
PM_START
PM_COMPLETE
CM_START
CM_COMPLETE
SPARE_REQUEST
SPARE_AVAILABLE
RESOURCE_BUSY
RESOURCE_AVAILABLE
PRODUCTION_CHANGE

Implement tests for:

- deterministic seed;
- exponential failure;
- competing risks;
- PF timing;
- successful diagnostic detection;
- missed detection;
- preventive maintenance;
- corrective maintenance;
- resource waiting;
- spare waiting;
- production loss;
- MTBF;
- MTTR;
- Ai;
- Ao;
- MTBM;
- MDT.

Do not implement UI.
Do not implement Petri-Pilot.
Do not implement AI.
```

---

# 97. FOURTH CURSOR AGENT PROMPT — PETRI-PILOT

```text
Implement Petri model generation and Petri-Pilot integration.

Constraints:

- Petri-Pilot is an external formal modelling engine.
- Keep it behind an adapter/interface.
- No Petri-Pilot-specific code in Domain.
- The generated Petri model must preserve source_entity_type and source_entity_id.
- Model generation must be deterministic for a fixed domain model.

Implement:

PetriModel
PetriPlace
PetriTransition
PetriArc
PetriModelGenerator
PetriPilotPort
PetriPilotMCPAdapter

Support:

validate
analyze
verify
simulate

External failures must be represented as typed infrastructure errors.

Add:
- mock adapter;
- integration tests;
- model generation tests;
- mapping tests.
```

---

# 98. FIFTH CURSOR AGENT PROMPT — AI ORCHESTRATOR

```text
Implement the AI Orchestrator.

Constraints:

LLM is not source of truth.

Pipeline:

LLM
→ structured DTO
→ schema validation
→ domain validation
→ provenance
→ user review
→ persistence

Implement:

AIProvider
AIOrchestrator
SystemGenerationService
EquipmentGenerationService
FailureModeGenerationService
MaintenanceGenerationService

AI must never:
- execute arbitrary SQL;
- execute shell commands;
- directly mutate database;
- invent source references;
- silently overwrite user data.

Unknown information must be represented as unknown or explicit engineering assumption.

Add mock AI provider and tests.
```

---

# 99. SIXTH CURSOR AGENT PROMPT — FRONTEND

```text
Implement the React frontend.

Use:

React
TypeScript
Vite
React Router
TanStack Query
MUI or Ant Design
React Flow
ECharts

Implement pages:

Systems
System Overview
Database
Equipment Schema
Reliability Model
Petri Model
Scenarios
Simulation
Results
AI Analysis

Start with:
- navigation;
- system list;
- system page;
- equipment table;
- failure mode table;
- maintenance table.

Do not implement fake backend data once API endpoints are available.

Use typed API clients.

Keep reusable components separate from feature-specific components.
```

---

# 100. SEVENTH CURSOR AGENT PROMPT — RESULTS

```text
Implement simulation result presentation.

Use actual SimulationRun and Metrics APIs.

Display:

Reliability
Availability
Maintainability
MTBF
MTTR
MTBM
MDT
Downtime
Production Loss
Production Availability
Failure Count
Maintenance Count
Diagnostic Count

Charts:

Reliability curve
Availability
Failure Pareto
Production loss Pareto
Maintenance workload
Spare consumption

Every displayed metric must identify:
- simulation;
- model version;
- scenario;
- seed where relevant.

Do not calculate engineering metrics independently in React.
All authoritative calculations belong to backend.
```

---

# 101. FINAL MVP ACCEPTANCE TEST

A fresh installation must support this flow:

```text
1. Start application.

2. Create system:
   Установка производства полистирола - 100

3. Enter description:
   Типовая установка производства полистирола
   из стирола, мощность 100 тыс. тонн в год.

4. AI generates equipment proposal.

5. User reviews proposal.

6. User accepts.

7. Equipment database is populated.

8. User edits equipment.

9. Failure modes are generated.

10. Failure distributions are generated.

11. PF Interval is visible/editable.

12. Maintenance tasks are generated.

13. Equipment topology is displayed.

14. Reliability model is generated.

15. Petri model is generated.

16. Petri-Pilot validates the model.

17. User creates simulation configuration.

18. User runs Monte Carlo.

19. Simulation runs asynchronously.

20. Results are stored.

21. User sees:
    Reliability
    Availability
    Maintainability
    MTBF
    MTTR
    MTBM
    MDT
    Production loss
    Production availability

22. User opens equipment metrics.

23. User opens event log.

24. User creates maintenance scenario.

25. User modifies diagnostic interval.

26. User reruns simulation.

27. User compares scenarios.

28. User asks AI:
    "Какие единицы оборудования дали
     наибольший вклад в потерю производства?"

29. AI answers from actual stored results.

30. User can trace important parameters
    back to their source/provenance.
```

---

# 102. FINAL ARCHITECTURAL INVARIANTS

Cursor agents must never violate these principles:

```text
1. Domain DB is source of truth.

2. LLM is an assistant, not an engineering authority.

3. All engineering parameters have provenance.

4. PF Interval is a first-class FailureMode property.

5. Explicit units are mandatory.

6. Petri-Pilot is behind an adapter.

7. Petri-Pilot does not replace RAM Engine.

8. RAM Engine is event-driven.

9. Monte Carlo uses deterministic seeds.

10. Model versions are immutable.

11. Simulation results reference exact model versions.

12. AI cannot execute arbitrary SQL.

13. AI cannot directly mutate DB.

14. FastAPI routers contain no business logic.

15. React contains no authoritative engineering calculations.

16. Long simulations run asynchronously.

17. External providers must be mockable.

18. Correctness takes priority over performance.

19. Every major engineering calculation has tests.

20. Every important result must be traceable
    to a model, scenario and simulation run.
```

---

# 103. TARGET END STATE

После завершения MVP архитектура должна выглядеть так:

```text
                         ┌──────────────────┐
                         │      Browser     │
                         └────────┬─────────┘
                                  │
                         ┌────────▼─────────┐
                         │     FastAPI      │
                         └────────┬─────────┘
                                  │
              ┌───────────────────┼────────────────────┐
              │                   │                    │
              ▼                   ▼                    ▼
       Application           AI Orchestrator      Simulation API
              │                   │                    │
              │          ┌────────┼────────┐           │
              │          ▼        ▼        ▼           │
              │       OpenAI  Fabricate Reference     │
              │                                      │
              └──────────────────┬───────────────────┘
                                 ▼
                         ┌───────────────┐
                         │ Domain Model  │
                         └───────┬───────┘
                                 │
                     ┌───────────┴───────────┐
                     │                       │
                     ▼                       ▼
             Reliability Model          Petri Model
                     │                       │
                     │                 Petri-Pilot
                     │                       │
                     ▼                       ▼
                RAM Engine             Formal Analysis
                     │                       │
                     └───────────┬───────────┘
                                 ▼
                          Simulation Results
                                 │
                  ┌──────────────┴──────────────┐
                  ▼                             ▼
             Results UI                     AI Analyst
```

---

# 104. PRINCIPAL ENGINEERING DECISION

Главное решение данного пакета:

> **Система должна иметь два связанных, но независимых представления одной промышленной системы:**

```text
Reliability Model
        │
        ├── RAM Simulation
        │
        └── Petri Model
               │
               └── Petri-Pilot
```

RAM model отвечает на вопрос:

> Что произойдет с надежностью, ремонтопригодностью, доступностью, производством и ресурсами при заданных стохастических отказах и стратегиях обслуживания?

Petri model отвечает на вопрос:

> Корректно ли формально представлена структура состояний, переходов, зависимостей и процессов системы?

Именно это разделение должно оставаться фундаментом проекта.

---

# 105. ПЕРВЫЙ ПРАКТИЧЕСКИЙ ШАГ

Cursor должен начинать не с генерации всей системы целиком.

Правильная последовательность:

```text
Step 1
Repository bootstrap

Step 2
Cursor rules

Step 3
Domain foundation

Step 4
Database + migrations

Step 5
API

Step 6
AI generation

Step 7
Reliability model

Step 8
RAM engine

Step 9
Petri-Pilot adapter

Step 10
Monte Carlo

Step 11
Metrics

Step 12
Frontend

Step 13
Scenarios

Step 14
AI Analyst

Step 15
OREDA / ISO

Step 16
Excel
```

На каждом шаге Cursor должен:

```text
implement
→ test
→ validate
→ document
→ commit
→ proceed
```

а не генерировать огромный объём кода одним проходом.

# END OF CURSOR DEVELOPMENT PACKAGE v1.0

# AI RELIABILITY MODELLING

## Техническое задание v1.0

**Версия:** 1.0
**Статус:** Baseline / Development Specification
**Тип системы:** Web application
**Назначение:** создание цифрового двойника промышленной установки, построение модели надёжности на основе Colored/Multilevel Petri Net и проведение Monte Carlo моделирования показателей Reliability, Availability, Maintainability и Production Availability.

---

# 1. Назначение системы

AI Reliability Modelling — браузерное приложение для инженерного моделирования надёжности промышленных технологических установок.

Система должна позволять пользователю:

1. создать описание промышленной установки на естественном языке;
2. автоматически сформировать первоначальную базу оборудования;
3. дополнить оборудование характеристиками, компонентами, связями и эксплуатационными данными;
4. сформировать Failure Modes и их вероятностные характеристики;
5. описать техническое обслуживание, диагностику, профилактические и корректирующие мероприятия;
6. задать PF Interval для каждого потенциального отказа;
7. сформировать топологическую схему оборудования;
8. автоматически построить формальную Petri-модель;
9. проверить Petri-модель;
10. провести Monte Carlo RAM simulation;
11. рассчитать показатели оборудования и системы;
12. рассчитать производственные потери;
13. рассчитать расход ресурсов, материалов и запасных частей;
14. сравнивать различные стратегии технического обслуживания;
15. задавать вопросы AI по построенной модели и результатам;
16. сохранять все версии модели и результаты расчётов;
17. обеспечивать воспроизводимость расчётов.

---

# 2. Пример использования

Пользователь вводит:

> Типовая установка производства полистирола из стирола, мощность 100 тыс. тонн в год.

Название:

> Установка производства полистирола - 100 (УПП-100)

AI должен сформировать первоначальную структуру:

```text
УПП-100
│
├── Подготовка сырья
├── Реакторный блок
├── Система охлаждения
├── Система циркуляции
├── Разделение продукта
├── Сушка
├── Грануляция
├── Транспортировка
├── Электроснабжение
├── КИПиА
└── Вспомогательные системы
```

После генерации пользователь должен иметь возможность полностью редактировать модель.

---

# 3. Основные архитектурные принципы

## 3.1. Domain Model является единственным источником истины

Главный источник данных:

```text
Domain Database
```

Не:

```text
Excel
LLM
Petri model
Simulation result
Fabricate
```

Все остальные представления являются производными.

```text
User
  │
  ▼
Domain Model
  │
  ├── Equipment Model
  ├── Reliability Model
  ├── Maintenance Model
  ├── Production Model
  │
  ▼
Petri Model
  │
  ├── validation
  ├── analysis
  └── simulation support
  │
  ▼
RAM Simulation Engine
  │
  ▼
Simulation Results
```

---

# 4. Архитектура системы

## 4.1. Логическая архитектура

```text
┌─────────────────────────────────────────────┐
│                 WEB UI                      │
│ React + TypeScript                          │
└──────────────────┬──────────────────────────┘
                   │ REST / SSE
                   ▼
┌─────────────────────────────────────────────┐
│              FastAPI Backend                │
├─────────────────────────────────────────────┤
│ API                                         │
│ Application Services                        │
│ Domain Services                             │
│ Validation                                  │
│ AI Orchestrator                             │
│ Scenario Manager                            │
│ Simulation Manager                          │
└───────┬──────────────┬──────────────┬───────┘
        │              │              │
        ▼              ▼              ▼
   PostgreSQL/       AI Layer       Simulation
   SQLite            │              Engine
                     ├─ OpenAI      │
                     ├─ Fabricate   │
                     └─ Petri-Pilot │
                                    │
                                    ▼
                              Monte Carlo RAM
```

---

# 5. Технологический стек

## Backend

* Python 3.12+
* FastAPI
* Pydantic v2
* SQLAlchemy 2
* Alembic
* NumPy
* SciPy
* pandas
* reliability
* lifelines
* optional Numba
* pytest
* httpx
* structlog

## Frontend

* React
* TypeScript
* Vite
* React Router
* TanStack Query
* MUI или Ant Design
* React Flow
* Apache ECharts

## Database

Development:

```text
SQLite
```

Production:

```text
PostgreSQL
```

ORM:

```text
SQLAlchemy
```

## Infrastructure

* Docker
* Docker Compose
* Redis — background jobs/cache при необходимости
* optional Celery/RQ
* Nginx
* object storage для больших simulation artifacts

## AI

* OpenAI API
* structured outputs
* tool calling
* AI Orchestrator

## MCP

* Petri-Pilot MCP
* Fabricate API/MCP adapter
* в дальнейшем OREDA/knowledge adapter

---

# 6. Ключевое архитектурное решение: Petri-Pilot и RAM Engine

Petri-Pilot не должен быть единственным вычислительным ядром надёжности.

## Petri-Pilot отвечает за:

* создание Petri model;
* структурную проверку;
* reachability;
* deadlock analysis;
* liveness;
* invariants;
* conformance;
* transition simulation;
* визуальное представление Petri net.

## RAM Engine отвечает за:

* Failure distributions;
* repair distributions;
* preventive maintenance;
* diagnostics;
* PF Interval;
* competing risks;
* spare parts;
* resources;
* downtime;
* production loss;
* Monte Carlo;
* Reliability;
* Availability;
* Maintainability;
* Operational Availability;
* Inherent Availability.

Таким образом:

```text
Petri-Pilot = formal process/state model

RAM Engine = engineering reliability simulation
```

---

# 7. Предметная модель

Основная структура:

```text
System
│
├── SystemVersion
│
├── Equipment
│   ├── EquipmentComponent
│   ├── EquipmentTaxonomy
│   ├── FailureMode
│   │   ├── FailureDistribution
│   │   └── PFInterval
│   │
│   └── MaintenanceTask
│       ├── MaintenanceDistribution
│       ├── MaintenanceEffect
│       ├── ResourceRequirement
│       └── SparePartRequirement
│
├── EquipmentConnection
├── ProductionFunction
├── ProductionImpact
│
├── ReliabilityModel
├── PetriModel
│
├── Scenario
│
└── Simulation
    ├── SimulationConfiguration
    ├── SimulationRun
    ├── SystemMetrics
    ├── EquipmentMetrics
    ├── FailureEvents
    ├── MaintenanceEvents
    ├── ProductionLossEvents
    └── ResourceConsumption
```

---

# 8. System

```text
System
```

Поля:

```text
id
name
description
plant_type
location
nominal_production
production_unit
production_period
commissioning_date
operating_regime
status
created_at
updated_at
```

Пример:

```json
{
  "name": "Установка производства полистирола - 100",
  "code": "УПП-100",
  "nominal_production": 100000,
  "production_unit": "t/year"
}
```

---

# 9. SystemVersion

Любое изменение инженерной модели должно создавать новую версию.

```text
SystemVersion
```

Поля:

```text
id
system_id
version
status
created_at
created_by
parent_version_id
change_summary
is_baseline
```

Статусы:

```text
DRAFT
VALIDATED
APPROVED
ARCHIVED
```

Simulation всегда ссылается на конкретный `SystemVersion`.

---

# 10. Equipment

```text
Equipment
```

Обязательные поля:

```text
id
system_version_id
tag
name
description
category
class
type
manufacturer
model
serial_number
commissioning_date
quantity
criticality
operating_mode
standby_mode
location
```

Пример:

```text
Category:
Rotating equipment

Class:
Pump

Type:
Centrifugal process pump
```

---

# 11. Taxonomy

Taxonomy должна быть расширяемой.

Не следует жёстко кодировать ISO 14224 в таблицах Equipment.

Модель:

```text
Taxonomy
│
└── TaxonomyNode
```

Примеры taxonomy:

```text
BUSINESS
ISO_14224
COMPANY
API
IEC
```

Для BUSINESS:

```text
Rotating equipment
    └── Pump
        └── Centrifugal process pump
```

Для ISO 14224 используется отдельное дерево.

Одна единица оборудования может иметь несколько taxonomy assignments.

---

# 12. EquipmentComponent

Компоненты оборудования:

```text
EquipmentComponent
```

Примеры для насоса:

```text
Impeller
Shaft
Bearing
Mechanical seal
Motor coupling
Casing
```

Поля:

```text
id
equipment_id
name
component_type
manufacturer
model
quantity
criticality
description
```

Компонент может иметь собственные Failure Modes.

---

# 13. EquipmentConnection

```text
EquipmentConnection
```

Поля:

```text
id
system_version_id
source_equipment_id
target_equipment_id
connection_type
direction
capacity
unit
is_critical
description
```

Типы:

```text
PROCESS
MATERIAL
ENERGY
ELECTRICAL
CONTROL
SIGNAL
UTILITY
```

---

# 14. FailureMode

FailureMode — одна из центральных сущностей модели.

```text
FailureMode
```

Поля:

```text
id
equipment_id
component_id
code
name
description

failure_class
failure_cause
failure_mechanism
failure_consequence

detectability
functional_effect
local_effect
system_effect

pf_interval_value
pf_interval_unit

failure_distribution_id

criticality
enabled

source_type
source_reference
confidence

created_at
updated_at
```

---

# 15. PF Interval

## Определение

PF Interval — время между появлением первых обнаружимых признаков потенциального отказа и фактическим функциональным отказом.

```text
PF Interval =
Functional Failure Time
-
Potential Failure Detection Time
```

Единицы:

```text
MINUTES
HOURS
DAYS
MONTHS
YEARS
```

Пример:

```text
PF Interval = 30 DAYS
```

означает, что первые обнаружимые признаки потенциального отказа могут появиться примерно за 30 дней до функционального отказа.

## Важно

PF Interval:

* не является MTBF;
* не является MTTR;
* не является периодом диагностики;
* не является временем ремонта;
* не является параметром failure distribution.

Он определяет **diagnostic window**.

---

# 16. Failure Distribution

```text
FailureDistribution
```

Поля:

```text
id
failure_mode_id
distribution_type
parameter_1
parameter_2
parameter_3
parameter_4
unit
min_value
max_value
```

Поддержать:

```text
EXPONENTIAL
WEIBULL
LOGNORMAL
NORMAL
GAMMA
UNIFORM
TRIANGULAR
CONSTANT
EMPIRICAL
```

Для Weibull:

```text
shape β
scale η
```

Для exponential:

```text
lambda
```

Все параметры должны иметь единицы измерения и provenance.

---

# 17. Provenance

Каждое инженерное значение должно иметь источник.

```text
ReferenceSource
```

Типы:

```text
OREDA
ISO_14224
USER_DEFINED
AI_ESTIMATE
ENGINEERING_ASSUMPTION
HISTORICAL_DATA
MANUFACTURER_DATA
```

Пример:

```text
Failure rate:
0.00012 / hour

Source:
OREDA-2015

Confidence:
HIGH
```

AI не должен выдавать AI-estimate как установленный инженерный факт.

---

# 18. OREDA

OREDA-2015 загружается в локальный reference database.

Предусмотреть:

```text
OREDAEquipmentClass
OREDAFailureMode
OREDAFailureRate
OREDADistribution
OREDARepairTime
OREDAReference
```

Пользователь должен видеть:

```text
Value
Source
Reference
Confidence
```

AI должен иметь возможность сказать:

> Для данного типа оборудования недостаточно данных.

И предложить:

```text
[Использовать OREDA]
[Использовать engineering estimate]
[Ввести вручную]
```

---

# 19. MaintenanceTask

Каждый maintenance task имеет тип:

```text
INSPECTION
DIAGNOSTIC
PREVENTIVE
CORRECTIVE
```

Поля:

```text
id
equipment_id
failure_mode_id
name
type

schedule_value
schedule_unit

condition_based
trigger_condition

maintenance_distribution_id
maintenance_effect_id

priority
enabled

source_type
source_reference
confidence
```

---

# 20. MaintenanceDistribution

Должен существовать отдельно от FailureDistribution.

Например:

```text
Repair duration
Inspection duration
Diagnostic duration
Mobilization time
Waiting time
Spare part lead time
```

Типы:

```text
CONSTANT
EXPONENTIAL
NORMAL
LOGNORMAL
WEIBULL
GAMMA
TRIANGULAR
UNIFORM
EMPIRICAL
```

---

# 21. MaintenanceEffect

MaintenanceEffect описывает результат выполнения обслуживания.

Примеры:

```text
RESTORE_TO_AS_NEW
RESTORE_TO_AS_BAD
REDUCE_FAILURE_RATE
RESET_FAILURE_AGE
REDUCE_REMAINING_LIFE
ELIMINATE_FAILURE_MODE
CHANGE_FAILURE_RATE_MULTIPLIER
```

Пример:

```json
{
  "effect_type": "CHANGE_FAILURE_RATE_MULTIPLIER",
  "value": 0.65
}
```

---

# 22. Diagnostics

Diagnostics — first-class object.

Пример:

```text
Vibration monitoring
Frequency: every 30 days
Detection probability: 0.85
```

Параметры:

```text
inspection_interval
detection_probability
false_positive_probability
false_negative_probability
diagnostic_duration
```

Диагностика должна учитывать PF Interval.

---

# 23. Модель диагностики с PF Interval

Если:

```text
Failure time = T
PF interval = P
```

то potential failure начинается:

```text
T_pf = T - P
```

Если диагностическое мероприятие происходит в:

```text
T_pf <= T_diagnostic < T
```

то система получает возможность обнаружить impending failure.

Вероятность обнаружения:

```text
P(detection) = diagnostic_detection_probability
```

Если обнаружение произошло:

```text
Potential Failure
        ↓
Detected
        ↓
Preventive Maintenance
        ↓
Restored
```

Если не произошло:

```text
Potential Failure
        ↓
Undetected
        ↓
Functional Failure
        ↓
Corrective Maintenance
```

---

# 24. ResourceRequirement

Каждое MaintenanceTask может потреблять ресурсы.

```text
ResourceRequirement
```

Примеры:

```text
Technician
Electrician
Mechanic
Crane
Mobile workshop
Inspection team
Specialist
```

Поля:

```text
resource_id
quantity
duration
unit
cost
```

---

# 25. SparePartRequirement

```text
SparePartRequirement
```

Поля:

```text
spare_part_id
quantity
unit_cost
lead_time
availability_probability
mandatory
```

Пример:

```text
Mechanical seal
quantity = 1
lead time = 7 days
```

---

# 26. Production Model

Reliability model должна быть связана с производственной функцией.

```text
ProductionFunction
```

Параметры:

```text
nominal_capacity
unit
time_basis
operating_factor
```

Production impact:

```text
ProductionImpact
```

Примеры:

```text
FULL_LOSS
PARTIAL_LOSS
NO_PRODUCTION_LOSS
THROUGHPUT_REDUCTION
QUALITY_LOSS
```

Например:

```text
Pump failure:
production reduction = 35%
```

---

# 27. Резервирование

Система должна поддерживать:

```text
1oo1
1oo2
2oo3
N+1
standby
cold standby
hot standby
```

Для оборудования:

```text
active
standby
failed
maintenance
```

Пример:

```text
P-101A + P-101B

Operating configuration:
1 active + 1 standby
```

---

# 28. Reliability Model

```text
ReliabilityModel
```

Содержит:

```text
system architecture
failure logic
maintenance logic
diagnostic logic
production logic
redundancy logic
dependencies
```

---

# 29. Petri Model

Petri model является производным представлением Reliability Model.

Минимальные элементы:

```text
Places
Transitions
Arcs
Tokens
Guards
Events
Properties
```

Типовая модель оборудования:

```text
          ┌──────────┐
          │   UP     │
          └────┬─────┘
               │
          Failure
               │
               ▼
        ┌─────────────┐
        │   FAILED    │
        └──────┬──────┘
               │
          Diagnosis
               │
               ▼
        ┌─────────────┐
        │   REPAIR    │
        └──────┬──────┘
               │
               ▼
              UP
```

С PF:

```text
UP
 │
 ▼
POTENTIAL_FAILURE
 │
 ├── detected ──► PREVENTIVE_MAINTENANCE
 │
 └── missed ────► FUNCTIONAL_FAILURE
                       │
                       ▼
                 CORRECTIVE_REPAIR
```

---

# 30. Petri-Pilot Adapter

Внутри приложения не должно быть прямого вызова MCP из business logic.

Использовать:

```text
PetriPilotAdapter
```

Интерфейс:

```python
class PetriPilotPort:

    async def validate(model): ...
    async def analyze(model): ...
    async def verify(model, property): ...
    async def simulate(model, events): ...
    async def conformance(model, event_log): ...
```

Реализация:

```text
PetriPilotMCPAdapter
```

Если API Petri-Pilot изменится, изменение должно потребовать только адаптера.

---

# 31. Petri validation

Перед simulation:

```text
1. Domain validation
2. Reliability validation
3. Petri generation
4. Petri structural validation
5. Petri analysis
6. Simulation readiness check
```

Model не может быть запущена при:

```text
missing failure distribution
invalid maintenance duration
broken equipment connection
undefined production impact
invalid PF interval
invalid Petri arc
deadlock where not expected
```

---

# 32. RAM Simulation Engine

Это отдельный Python-модуль.

```text
ram_engine/
├── distributions/
├── events/
├── state_machine/
├── maintenance/
├── diagnostics/
├── production/
├── resources/
├── monte_carlo/
├── metrics/
└── validation/
```

Основной интерфейс:

```python
run_simulation(
    model,
    configuration,
    seed
) -> SimulationResult
```

---

# 33. Simulation configuration

```text
SimulationConfiguration
```

Поля:

```text
simulation_horizon
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

Пример:

```text
Horizon: 20 years
Runs: 10,000
Seed: 12345
Confidence: 95%
```

---

# 34. Monte Carlo

Каждая реализация:

```text
Run #1
Run #2
...
Run #N
```

имеет независимый random stream.

Рекомендуется использовать deterministic seed derivation:

```text
seed_i = hash(master_seed, run_id)
```

Один и тот же:

```text
model version
scenario
configuration
seed
```

должен давать воспроизводимый результат.

---

# 35. Event-driven simulation

Simulation должна быть event-driven, а не timestep-based.

Основные события:

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

---

# 36. Состояния оборудования

Минимальный state machine:

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

---

# 37. Failure generation

Для каждого FailureMode simulation engine должен:

1. выбрать distribution;
2. сгенерировать failure time;
3. вычислить potential failure time:

```text
Tpf = Tf - PFInterval
```

4. поставить события;
5. учитывать preventive maintenance;
6. учитывать диагностические проверки.

---

# 38. Competing failures

Если оборудование имеет:

```text
Failure Mode A
Failure Mode B
Failure Mode C
```

должны поддерживаться competing risks.

Первый наступивший failure становится активным состоянием.

После восстановления должен быть определён:

```text
renewal model
```

или:

```text
as-good-as-new
as-bad-as-old
partial restoration
```

---

# 39. Метрики Reliability

Reliability:

```text
R(t) = P(T_failure > t)
```

В Monte Carlo:

```text
R(t) =
number of runs surviving to t
/
total runs
```

Должны отображаться:

```text
R(1 year)
R(5 years)
R(10 years)
R(horizon)
```

---

# 40. MTBF

Для repairable equipment:

```text
MTBF =
total operating time
/
number of functional failures
```

Также допускается аналитический расчёт для соответствующих distribution.

---

# 41. MTTR

```text
MTTR =
total corrective repair time
/
number of corrective repairs
```

При необходимости отдельно:

```text
Active Repair Time
Waiting Time
Diagnosis Time
Mobilization Time
Spare Waiting Time
```

---

# 42. Inherent / Technical Availability

По принятому определению:

```text
Technical Availability / Inherent Availability:

Ai = MTBF / (MTBF + MTTR)
```

В интерфейсе необходимо явно показывать definition.

---

# 43. Operational Availability

Принятое определение:

```text
Ao = MTBM / (MTBM + MDT)
```

где:

```text
MTBM = Mean Time Between Maintenance
MDT = Mean Down Time
```

MDT включает фактическое downtime, обусловленное моделью:

```text
failure
diagnosis
waiting
repair
resource
spare
logistics
```

---

# 44. Maintainability

Основной показатель:

```text
M(t) = P(T_repair <= t)
```

Также:

```text
MTTR
repair time distribution
90th percentile repair time
95th percentile repair time
```

---

# 45. Production Availability

Дополнительно рассчитывается:

```text
Production Availability =
actual production
/
nominal production
```

Например:

```text
Nominal = 100,000 t/year
Actual = 96,400 t/year

Production Availability = 96.4%
```

---

# 46. Production Loss

Для каждого события:

```text
loss_rate
duration
lost_production
```

Общая формула:

```text
Production Loss =
Σ(loss_rate × nominal_rate × duration)
```

Результаты:

```text
tons
%
days
```

---

# 47. System Metrics

Минимальный dashboard:

```text
Reliability
Inherent Availability
Operational Availability
Maintainability
MTBF
MTTR
MTBM
MDT

Total failures
Total downtime
Production loss
Production availability

Corrective maintenance
Preventive maintenance
Diagnostic activities

Resource consumption
Spare parts consumption
Maintenance cost
```

---

# 48. Equipment Metrics

Для каждого оборудования:

```text
Failure count
Failure frequency
MTBF
MTTR
MTBM
MDT
Ai
Ao
Maintainability
Downtime
Production loss
PM count
CM count
Diagnostic count
Detected potential failures
Missed potential failures
Spare consumption
Maintenance cost
```

---

# 49. Event Log

Simulation должна сохранять события.

```text
FailureEvent
MaintenanceEvent
DiagnosticEvent
ProductionLossEvent
ResourceEvent
SparePartEvent
```

FailureEvent:

```text
simulation_run_id
timestamp
equipment_id
component_id
failure_mode_id
failure_type
detected
pf_interval
downtime_start
downtime_end
```

---

# 50. Scenario

Scenario позволяет изменять maintenance policy без изменения baseline.

```text
Scenario
```

Пример:

```text
Baseline
Scenario A: diagnostics every 30 days
Scenario B: diagnostics every 14 days
Scenario C: diagnostics every 60 days
```

---

# 51. Scenario Changes

```text
ScenarioChange
```

Поддержать:

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

# 52. Versioning

Simulation должна ссылаться на:

```text
system_version
scenario_version
model_version
simulation_configuration
random_seed
software_version
```

Это обеспечивает auditability.

---

# 53. AI Architecture

Главный AI-компонент:

```text
Reliability Engineering Orchestrator
```

Не следует создавать множество независимых агентов на MVP.

AI получает tools:

```text
get_system
get_equipment
get_failure_modes
get_maintenance
get_reference_data
validate_model
generate_equipment
generate_failure_modes
generate_maintenance
create_petri_model
validate_petri
run_simulation
get_results
compare_scenarios
```

---

# 54. AI role

AI:

```text
ORCHESTRATOR
ANALYST
DATA GENERATOR
ENGINEERING ASSISTANT
```

AI не должен быть:

```text
database
calculation engine
source of engineering truth
```

Все AI-generated values должны проходить validation.

---

# 55. AI generation pipeline

```text
User description
       │
       ▼
AI interpretation
       │
       ▼
Structured proposal
       │
       ▼
Schema validation
       │
       ▼
Engineering validation
       │
       ▼
User review
       │
       ▼
Persist
```

AI не должен напрямую выполнять:

```sql
INSERT
UPDATE
DELETE
```

без domain service.

---

# 56. AI generation result

AI должен возвращать структурированный JSON.

Пример:

```json
{
  "equipment": [],
  "failure_modes": [],
  "maintenance_tasks": [],
  "assumptions": [],
  "warnings": [],
  "missing_information": []
}
```

---

# 57. Недостаток данных

AI обязан явно сообщать:

```text
KNOWN
INFERRED
ESTIMATED
UNKNOWN
```

Например:

```text
Failure rate:
UNKNOWN

Suggested source:
OREDA

Alternative:
AI estimate

Confidence:
LOW
```

---

# 58. AI Chat

Чат должен быть context-aware.

Контекст:

```text
System
System Version
Scenario
Simulation
Selected Equipment
Selected Failure Mode
```

Пример вопроса:

> Почему у P-101 такая низкая availability?

AI должен получить реальные данные simulation и сформировать объяснение.

---

# 59. Примеры AI вопросов

```text
Почему снизилась availability?
Какие 10 отказов дают максимальные потери?
Какие насосы наиболее критичны?
Какой failure mode чаще всего приводит к остановке?
Сколько запасных частей потреблено?
Какие диагностики предотвратили отказы?
Сколько отказов было пропущено диагностикой?
Что произойдёт, если сократить интервал диагностики с 30 до 14 дней?
```

---

# 60. UI

Главный экран:

```text
Systems
────────────────────────────
УПП-100
НПЗ-1
Компрессорная станция
...
             [+ Создать систему]
```

---

# 61. System Page

Tabs:

```text
Overview
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

# 62. Database UI

Табличный интерфейс:

```text
Equipment
Failure Modes
Maintenance
Resources
Spare Parts
Connections
Production
```

Поддержать:

```text
filter
sort
search
inline edit
bulk edit
import
export
```

---

# 63. Equipment card

Показывать:

```text
Tag
Name
Category
Class
Type
Criticality

Failure Modes
PF Intervals
MTBF
MTTR
Availability

Maintenance Tasks
Diagnostics
```

---

# 64. Equipment topology

Использовать graph editor.

Ноды:

```text
Equipment
```

Edges:

```text
process
energy
control
electrical
utility
```

Функции:

```text
zoom
pan
select
filter
highlight critical path
show failure state
show production impact
```

---

# 65. Petri UI

Пользователь должен видеть:

```text
places
transitions
arcs
tokens
equipment mapping
failure states
maintenance states
```

Поддержать:

```text
zoom
pan
collapse equipment
expand equipment
highlight selected equipment
highlight failure path
```

---

# 66. Mapping Domain ↔ Petri

Каждый Petri element должен иметь metadata:

```text
source_entity_type
source_entity_id
```

Например:

```text
place: P101_FAILED
equipment_id: P101
state: FAILED
```

Это позволяет кликнуть Petri node и открыть оборудование.

---

# 67. Simulation UI

Форма:

```text
Simulation horizon
Number of runs
Random seed
Warm-up period
Confidence level
```

Кнопка:

```text
[Провести моделирование]
```

Во время выполнения:

```text
Preparing model
Validating
Starting Monte Carlo
Run 1 / 10000
Run 5000 / 10000
Completed
```

---

# 68. Simulation jobs

Simulation не должна выполняться в HTTP request.

Использовать background job.

Статусы:

```text
QUEUED
VALIDATING
RUNNING
COMPLETED
FAILED
CANCELLED
```

Frontend получает progress через SSE/WebSocket.

---

# 69. Results Dashboard

Основной экран:

```text
┌─────────────┬─────────────┬─────────────┐
│ Reliability │ Availability│ Maintainab. │
│   97.2 %    │   94.8 %    │    98 %     │
└─────────────┴─────────────┴─────────────┘

Production loss: 3,450 t/year
Downtime: 17.4 days/year
Failures: 184/year
```

Графики:

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

# 70. Confidence intervals

Для Monte Carlo metrics отображать:

```text
mean
median
P5
P50
P95
confidence interval
```

Например:

```text
Production Loss

Mean: 3,420 t/year
P5:   1,800
P50:  3,100
P95:  6,900
```

---

# 71. Scenario Comparison

Таблица:

```text
Metric              Baseline    Scenario A    Scenario B
---------------------------------------------------------
Availability
MTBF
MTTR
Downtime
Production Loss
PM Count
CM Count
Diagnostic Count
Spare Cost
Maintenance Cost
```

Также:

```text
Δ Availability
Δ Production Loss
Δ Maintenance Cost
```

---

# 72. Excel

Excel не является database.

Используется для:

```text
Import
Export
Review
Engineering exchange
```

Файлы:

```text
equipment.xlsx
failure_modes.xlsx
maintenance.xlsx
resources.xlsx
spares.xlsx
connections.xlsx
```

При import:

```text
Excel
 ↓
Parser
 ↓
Pydantic validation
 ↓
Domain validation
 ↓
Preview
 ↓
Commit
```

---

# 73. API

Base:

```text
/api/v1
```

## Systems

```http
GET    /systems
POST   /systems
GET    /systems/{id}
PATCH  /systems/{id}
DELETE /systems/{id}
```

## Versions

```http
GET  /systems/{id}/versions
POST /systems/{id}/versions
GET  /versions/{id}
```

## Equipment

```http
GET    /versions/{id}/equipment
POST   /versions/{id}/equipment
GET    /equipment/{id}
PATCH  /equipment/{id}
DELETE /equipment/{id}
```

## Failure Modes

```http
GET   /equipment/{id}/failure-modes
POST  /equipment/{id}/failure-modes
PATCH /failure-modes/{id}
```

## Maintenance

```http
GET   /equipment/{id}/maintenance
POST  /equipment/{id}/maintenance
PATCH /maintenance/{id}
```

## Petri

```http
POST /versions/{id}/petri/generate
POST /petri/{id}/validate
POST /petri/{id}/analyze
```

## Simulation

```http
POST /simulations
GET  /simulations/{id}
GET  /simulations/{id}/status
GET  /simulations/{id}/results
GET  /simulations/{id}/events
```

## Scenarios

```http
GET  /versions/{id}/scenarios
POST /versions/{id}/scenarios
POST /scenarios/{id}/simulate
GET  /scenarios/{id}/compare
```

## AI

```http
POST /ai/generate-system
POST /ai/generate-equipment
POST /ai/generate-failure-modes
POST /ai/generate-maintenance
POST /ai/chat
```

---

# 74. Основные DB tables

Минимальный production schema:

```text
systems
system_versions

equipment
equipment_components

taxonomies
taxonomy_nodes
equipment_taxonomy

failure_modes
failure_distributions

maintenance_tasks
maintenance_distributions
maintenance_effects

resources
resource_requirements

spare_parts
spare_part_requirements

equipment_connections

production_functions
production_impacts

reliability_models
petri_models

scenarios
scenario_changes

simulation_configurations
simulation_runs

system_metrics
equipment_metrics

failure_events
maintenance_events
diagnostic_events
production_loss_events

resource_consumption
spare_part_consumption

reference_sources
reference_parameters

ai_runs
ai_generated_values

audit_events
```

---

# 75. Audit

Каждое изменение engineering data:

```text
who
when
what
old value
new value
source
reason
```

AI-generated values должны иметь:

```text
ai_run_id
prompt/context hash
model
timestamp
confidence
```

---

# 76. Validation levels

## Level 1 — Schema

Pydantic:

```text
types
required fields
units
ranges
enums
```

## Level 2 — Domain

```text
PF interval > 0
repair time > 0
failure parameters valid
production impact valid
connections valid
```

## Level 3 — Engineering

```text
failure mode has distribution
maintenance has duration
critical equipment has production impact
diagnostic has detection probability
```

## Level 4 — Petri

```text
structural validity
reachability
deadlock
liveness
invariants
```

## Level 5 — Simulation

```text
model executable
all distributions supported
all resources resolvable
production function defined
```

---

# 77. Units

Internal canonical units:

```text
time: minutes
mass: kg
energy: MJ
power: kW
cost: project currency
```

UI может отображать:

```text
minutes
hours
days
months
years
```

PF Interval обязательно хранить:

```text
value
unit
```

а не только нормализованное число.

---

# 78. Error handling

API errors:

```json
{
  "error": {
    "code": "INVALID_PF_INTERVAL",
    "message": "PF Interval must be greater than zero",
    "entity": "failure_mode",
    "entity_id": "..."
  }
}
```

---

# 79. Security

MVP:

```text
single-user
```

Но архитектура должна позволять добавить:

```text
users
organizations
roles
permissions
```

Secrets:

```text
OPENAI_API_KEY
FABRICATE_API_KEY
PETRI_PILOT_URL
```

никогда не хранить в DB.

---

# 80. Logging

Structured JSON logging:

```text
timestamp
level
service
request_id
system_id
simulation_id
event
duration
error
```

AI calls:

```text
ai_model
token_usage
latency
tool_calls
```

---

# 81. Project structure

```text
ai-reliability-modelling/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── domain/
│   │   │   ├── equipment/
│   │   │   ├── reliability/
│   │   │   ├── maintenance/
│   │   │   ├── production/
│   │   │   └── simulation/
│   │   ├── application/
│   │   ├── infrastructure/
│   │   │   ├── db/
│   │   │   ├── mcp/
│   │   │   ├── ai/
│   │   │   └── files/
│   │   ├── simulation/
│   │   └── main.py
│   │
│   ├── migrations/
│   └── tests/
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── features/
│   │   ├── api/
│   │   ├── hooks/
│   │   └── types/
│
├── reference_data/
│   ├── oreda/
│   └── iso14224/
│
├── docker/
├── docs/
├── scripts/
├── docker-compose.yml
├── .env.example
└── README.md
```

---

# 82. Cursor rules

Создать:

```text
.cursor/rules/
```

## Rule 1 — Domain Source of Truth

LLM outputs are proposals.

Domain database is authoritative.

## Rule 2 — No business logic in routers

FastAPI routers call application services.

## Rule 3 — MCP isolation

Never call MCP directly from domain logic.

Use adapters.

## Rule 4 — Deterministic simulation

Every simulation must have explicit seed.

## Rule 5 — Immutable versions

Simulation cannot silently use modified model.

## Rule 6 — Provenance

Every generated engineering parameter must have source.

## Rule 7 — No arbitrary SQL from LLM

AI uses typed tools.

## Rule 8 — Test engineering formulas

All RAM metrics require automated tests.

## Rule 9 — Units

Never mix time units implicitly.

## Rule 10 — Long-running tasks

Simulation cannot block HTTP requests.

---

# 83. Testing

## Unit tests

Test:

```text
distributions
PF interval
failure generation
diagnostics
maintenance
resources
spares
production loss
metrics
```

## Integration tests

```text
API → DB
AI → validation
Domain → Petri
Petri adapter → Petri-Pilot
Simulation → DB
```

## Golden tests

Для фиксированной модели:

```text
seed = 12345
```

ожидается стабильный результат в заданном tolerance.

---

# 84. Mathematical tests

Exponential:

```text
R(t) = exp(-λt)
```

Availability:

```text
Ai = MTBF/(MTBF+MTTR)
```

Operational:

```text
Ao = MTBM/(MTBM+MDT)
```

Production:

```text
Loss = Σ rate × duration
```

PF:

```text
Tpf = Tf - PF
```

Все должны иметь dedicated tests.

---

# 85. Demo dataset

Создать демонстрационную модель:

```text
УПП-100
```

Минимум:

```text
50–100 equipment items
```

Типы:

```text
Pumps
Compressors
Heat exchangers
Reactors
Valves
Motors
Electrical equipment
Instrumentation
Tanks
Filters
Dryers
Granulators
```

Для каждого:

```text
failure modes
failure distributions
PF intervals
maintenance tasks
diagnostics
production impacts
```

---

# 86. Демонстрационный сценарий PF

Для насоса:

```text
Equipment:
P-101

Failure mode:
Mechanical seal degradation

Failure distribution:
Weibull

PF Interval:
14 days

Diagnostic:
Vibration/condition monitoring

Interval:
7 days

Detection probability:
0.85

Preventive maintenance:
Seal replacement

Repair duration:
1 hour
```

Simulation должна показать:

```text
detected potential failures
missed potential failures
functional failures
prevented downtime
actual downtime
production loss
```

---

# 87. MVP

MVP должен включать:

### Phase 1

```text
System creation
AI equipment generation
Equipment CRUD
Failure Modes
Maintenance Tasks
PF Interval
SQLite
```

### Phase 2

```text
Equipment graph
Production model
Petri generation
Petri-Pilot validation
```

### Phase 3

```text
RAM Engine
Monte Carlo
Failure simulation
Maintenance simulation
Availability
MTBF
MTTR
Production loss
```

### Phase 4

```text
Diagnostics
PF detection
Scenarios
Scenario comparison
```

### Phase 5

```text
OREDA
ISO 14224
Excel
AI Analyst
```

---

# 88. Post-MVP

Следующие функции:

```text
Maintenance optimization
Cost optimization
Inspection optimization
Spare stock optimization
Resource optimization
Condition-based maintenance
Bayesian updating
Historical data calibration
Digital twin integration
SCADA integration
CMMS integration
```

---

# 89. Future optimization

Целевая задача:

```text
minimize
    production_loss_cost
  + maintenance_cost
  + spare_cost
  + diagnostic_cost
  + downtime_cost
```

при ограничениях:

```text
Availability >= target
Reliability >= target
resources <= capacity
spares <= budget
```

Optimization не входит в v1.0, но domain model должна позволять её добавить.

---

# 90. Docker

MVP:

```text
docker-compose.yml
```

Services:

```text
frontend
backend
database
redis
petri-pilot
```

Опционально:

```text
worker
nginx
```

Локальный URL:

```text
http://localhost:18080
```

---

# 91. Environment

```env
APP_ENV=development

DATABASE_URL=sqlite:///./data/app.db

OPENAI_API_KEY=
OPENAI_MODEL=

FABRICATE_API_URL=
FABRICATE_API_KEY=

PETRI_PILOT_URL=

REDIS_URL=

SIMULATION_DEFAULT_SEED=12345
```

---

# 92. Deployment

Поддержать два режима.

## Local

```text
Docker Compose
localhost:18080
```

## Remote

```text
Linux server
Docker Compose
reverse proxy
HTTPS
PostgreSQL
```

---

# 93. API versioning

Использовать:

```text
/api/v1
```

Breaking changes:

```text
/api/v2
```

---

# 94. Model lifecycle

```text
CREATED
   ↓
GENERATED
   ↓
EDITING
   ↓
VALIDATING
   ↓
VALIDATED
   ↓
SIMULATION_READY
   ↓
SIMULATED
```

---

# 95. Simulation lifecycle

```text
CREATED
 ↓
QUEUED
 ↓
VALIDATING
 ↓
RUNNING
 ↓
AGGREGATING
 ↓
COMPLETED
```

При ошибке:

```text
FAILED
```

---

# 96. Главный пользовательский workflow

```text
1. Создать систему
       ↓
2. Ввести описание
       ↓
3. AI генерирует оборудование
       ↓
4. Пользователь проверяет
       ↓
5. AI/OREDA генерирует Failure Modes
       ↓
6. Пользователь проверяет PF Interval
       ↓
7. AI формирует maintenance
       ↓
8. Пользователь корректирует
       ↓
9. Создать equipment schema
       ↓
10. Создать Reliability Model
       ↓
11. Создать Petri Model
       ↓
12. Validate Petri
       ↓
13. Запустить Monte Carlo
       ↓
14. Получить RAM results
       ↓
15. Анализировать production loss
       ↓
16. Создать Scenario
       ↓
17. Изменить maintenance
       ↓
18. Повторить simulation
       ↓
19. Сравнить scenarios
```

---

# 97. Критически важное различие моделей

В системе должны существовать четыре разных уровня.

## Level 1 — Digital Twin

```text
Что существует физически?
```

## Level 2 — Reliability Model

```text
Как оборудование отказывает и восстанавливается?
```

## Level 3 — Petri Model

```text
Как эти состояния и переходы формализуются?
```

## Level 4 — RAM Simulation

```text
Какова статистика поведения системы во времени?
```

Нельзя объединять эти уровни в одну сущность.

---

# 98. Acceptance Criteria v1.0

Система считается реализованной, если пользователь может:

### AC-01

Создать:

```text
УПП-100
```

из текстового описания.

### AC-02

Получить автоматически сгенерированное оборудование.

### AC-03

Изменить оборудование вручную.

### AC-04

Добавить Failure Mode.

### AC-05

Задать:

```text
Weibull
β
η
PF Interval
```

### AC-06

Задать:

```text
Diagnostic interval
Detection probability
```

### AC-07

Задать maintenance task.

### AC-08

Увидеть equipment topology.

### AC-09

Создать Petri model.

### AC-10

Проверить её через Petri-Pilot.

### AC-11

Запустить Monte Carlo.

### AC-12

Получить:

```text
Reliability
Availability
Maintainability
MTBF
MTTR
MTBM
MDT
Production loss
Downtime
```

### AC-13

Получить equipment-level metrics.

### AC-14

Получить failure events.

### AC-15

Получить maintenance events.

### AC-16

Получить resource/spare consumption.

### AC-17

Создать maintenance scenario.

### AC-18

Изменить diagnostic interval.

### AC-19

Перезапустить simulation.

### AC-20

Сравнить scenarios.

### AC-21

Задать вопрос AI по результатам.

---

# 99. Cursor implementation backlog

## Epic 1 — Foundation

```text
T001 Create repository
T002 Setup Python
T003 Setup FastAPI
T004 Setup React
T005 Setup Docker
T006 Setup SQLAlchemy
T007 Setup Alembic
T008 Setup testing
```

## Epic 2 — Domain

```text
T009 System
T010 SystemVersion
T011 Equipment
T012 EquipmentComponent
T013 Taxonomy
T014 FailureMode
T015 FailureDistribution
T016 PFInterval
T017 MaintenanceTask
T018 MaintenanceDistribution
T019 MaintenanceEffect
T020 Resources
T021 SpareParts
T022 ProductionModel
```

## Epic 3 — UI

```text
T023 Systems page
T024 System page
T025 Equipment table
T026 Failure mode editor
T027 Maintenance editor
T028 Equipment graph
```

## Epic 4 — AI

```text
T029 AI Orchestrator
T030 Structured equipment generation
T031 Failure generation
T032 Maintenance generation
T033 Provenance
T034 AI chat
```

## Epic 5 — Petri

```text
T035 Reliability → Petri compiler
T036 Petri adapter
T037 Petri validation
T038 Petri analysis
T039 Petri viewer
```

## Epic 6 — RAM

```text
T040 Distribution engine
T041 Failure engine
T042 PF engine
T043 Diagnostic engine
T044 Maintenance engine
T045 Resource engine
T046 Spare engine
T047 Production engine
T048 Monte Carlo
T049 Metrics
```

## Epic 7 — Simulation UI

```text
T050 Simulation configuration
T051 Background jobs
T052 Progress
T053 Results dashboard
T054 Event viewer
```

## Epic 8 — Scenarios

```text
T055 Scenario model
T056 Scenario changes
T057 Scenario simulation
T058 Scenario comparison
```

## Epic 9 — Reference Data

```text
T059 OREDA ingestion
T060 ISO taxonomy ingestion
T061 Reference browser
T062 Provenance UI
```

## Epic 10 — Excel

```text
T063 Excel export
T064 Excel import
T065 Import validation
```

## Epic 11 — Quality

```text
T066 Unit tests
T067 Integration tests
T068 Golden simulation tests
T069 E2E tests
T070 Docker deployment test
```

---

# 100. Definition of Done

Feature считается готовой только если:

```text
✓ domain model exists
✓ migration exists
✓ API exists
✓ validation exists
✓ UI exists where applicable
✓ tests exist
✓ logging exists
✓ provenance exists
✓ documentation exists
```

Для simulation дополнительно:

```text
✓ deterministic seed
✓ reproducibility test
✓ performance test
✓ metrics test
```

---

# 101. Основные нефункциональные требования (NFR)

## NFR-01

UI должен работать в современном Chromium browser.

## NFR-02

API должен быть stateless, кроме DB/job state.

## NFR-03

Simulation должна выполняться асинхронно.

## NFR-04

Модель должна быть versioned.

## NFR-05

Результат должен быть воспроизводим.

## NFR-06

AI не должен напрямую менять DB.

## NFR-07

Все engineering assumptions должны быть видимы.

## NFR-08

Любой simulation result должен быть связан с точной версией модели.

## NFR-09

Petri-Pilot должен быть заменяемым через adapter.

## NFR-10

RAM Engine не должен зависеть от UI.

---

# 102. Итоговая архитектурная схема

```text
                         USER
                           │
                           ▼
                    ┌─────────────┐
                    │   WEB UI    │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   FastAPI   │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌────────────┐
        │ AI       │ │ Domain   │ │ Simulation │
        │Orchestr. │ │ Services │ │ Manager    │
        └────┬─────┘ └────┬─────┘ └─────┬──────┘
             │            │              │
       ┌─────┴─────┐      │        ┌────┴──────┐
       │           │      │        │           │
       ▼           ▼      ▼        ▼           ▼
   Fabricate   OpenAI   Database  RAM Engine  Results
                            │
                            ▼
                     Reliability Model
                            │
                            ▼
                       Petri Compiler
                            │
                            ▼
                     Petri-Pilot MCP
                            │
                            ▼
                     Validated Petri Net
```

---

# 103. Ключевой принцип v1.0

Система должна быть построена не как:

```text
LLM → Petri → answer
```

а как:

```text
                    USER DESCRIPTION
                           │
                           ▼
                     AI GENERATION
                           │
                           ▼
                   DIGITAL TWIN MODEL
                           │
                           ▼
                  RELIABILITY MODEL
                           │
                ┌──────────┴──────────┐
                ▼                     ▼
          PETRI MODEL             RAM MODEL
                │                     │
                ▼                     ▼
         PETRI-PILOT             MONTE CARLO
         VALIDATION                  │
                │                     │
                └──────────┬──────────┘
                           ▼
                     RAM RESULTS
                           │
                           ▼
                      AI ANALYST
```

Главный источник истины — **версионированная инженерная модель системы**.

Petri Model — её формальное производное представление.

RAM Engine — специализированный вычислительный слой.

AI — интеллектуальный интерфейс и инженерный помощник, но не источник истины.

PF Interval — отдельный параметр каждого Failure Mode и ключевой элемент связи между диагностикой, condition-based maintenance и фактическим отказом.

---

# 104. Результат разработки v1.0

После завершения v1.0 пользователь должен иметь возможность пройти полный путь:

```text
"Типовая установка производства полистирола
из стирола, мощность 100 тыс. тонн в год"
```

↓

```text
AI creates digital twin
```

↓

```text
Equipment database
+
Failure modes
+
PF intervals
+
Diagnostics
+
Maintenance
+
Resources
+
Spares
+
Production impacts
```

↓

```text
Equipment topology
```

↓

```text
Reliability Model
```

↓

```text
Colored / Multilevel Petri Model
```

↓

```text
Petri-Pilot validation
```

↓

```text
Monte Carlo RAM simulation
```

↓

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
Resource Consumption
Spare Consumption
```

↓

```text
Scenario:
"Diagnostic interval = 14 days"
```

↓

```text
Monte Carlo
```

↓

```text
Baseline vs Scenario comparison
```

↓

```text
AI Engineering Analysis
```

Именно эта цепочка является **целевой end-to-end функциональностью AI Reliability Modelling v1.0**.

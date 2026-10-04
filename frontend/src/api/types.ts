/** Typed API models aligned with backend OpenAPI / Pydantic DTOs. */

export interface System {
  id: string
  name: string
  description: string | null
  created_by: string | null
  created_at: string
}

export interface SystemVersion {
  id: string
  system_id: string
  version_number: number
  status: string
  lineage_id: string
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface Equipment {
  id: string
  version_id: string
  lineage_id: string
  tag: string
  name: string
  description: string | null
  parent_id: string | null
  category: string | null
  equipment_class: string | null
  equipment_type: string | null
  location: string | null
  quantity: number
  criticality: string
  operating_mode: string
  standby_mode: string
  is_repairable: boolean
}

export interface EquipmentConnection {
  id: string
  version_id: string
  lineage_id: string
  source_id: string
  target_id: string
  connection_type: string
  description: string | null
}

export interface GenerationJob {
  id: string
  provider: string
  status: string
  description: string
  system_id: string | null
  version_id: string | null
  proposal_id: string | null
  conversation_id: string | null
  progress_pct: number
  progress_message: string | null
  error_code: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface ProposalItem {
  id: string
  item_type: string
  item_key: string
  payload: Record<string, unknown>
  decision: string
  edited_payload: Record<string, unknown> | null
  sort_order: number
}

export interface Proposal {
  id: string
  generation_job_id: string | null
  provider: string
  status: string
  title: string
  payload: Record<string, unknown>
  provenance: Record<string, unknown>
  items: ProposalItem[]
  system_id: string | null
  version_id: string | null
}

export interface CommitResult {
  proposal_id: string
  system_id: string
  version_id: string
  created_equipment: number
  created_connections: number
  status: string
}

export type ScenarioChangeType =
  | 'CHANGE_DIAGNOSTIC_INTERVAL'
  | 'CHANGE_DETECTION_PROBABILITY'
  | 'CHANGE_PM_INTERVAL'
  | 'CHANGE_MAINTENANCE_DISTRIBUTION'
  | 'CHANGE_RESOURCE'
  | 'CHANGE_SPARE_STOCK'
  | 'CHANGE_FAILURE_PARAMETER'
  | 'ENABLE_TASK'
  | 'DISABLE_TASK'

export interface ScenarioChange {
  id: string
  scenario_version_id: string
  change_type: ScenarioChangeType
  target_lineage_id: string
  parameters: Record<string, unknown>
  sort_order: number
}

export interface ScenarioVersion {
  id: string
  scenario_id: string
  version_number: number
  scenario_hash: string
  created_at: string
  changes: ScenarioChange[]
}

export interface Scenario {
  id: string
  version_id: string
  name: string
  description: string | null
  current_version_id: string | null
  created_at: string
  updated_at: string
  current_version: ScenarioVersion | null
}

export interface SimulationStatus {
  id: string
  version_id: string
  scenario_version_id: string | null
  status: string
  progress: number
  completed_runs: number
  total_runs: number
  random_seed: number
  model_hash: string
  scenario_hash: string
  configuration_hash: string
  software_version: string
  simulation_fingerprint: string
  error_message: string | null
  started_at?: string | null
  completed_at?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface MetricSummary {
  mean: number | null
  median: number | null
  p5: number | null
  p50: number | null
  p95: number | null
  ci_low: number | null
  ci_high: number | null
  sample_size: number
}

export interface ProportionSummary {
  value: number | null
  successes: number
  trials: number
  ci_low: number | null
  ci_high: number | null
  method: string
}

export interface ParetoItem {
  key: string
  count: number
  share: number
}

export interface EquipmentAggregateMetrics {
  equipment_id: string
  failure_count: MetricSummary
  downtime_minutes: MetricSummary
  mtbf_minutes: MetricSummary
  mttr_minutes: MetricSummary
  ai: MetricSummary
  pm_count: MetricSummary
  cm_count: MetricSummary
  detection_count: MetricSummary
}

export interface SystemAggregateMetrics {
  number_of_runs: number
  completed_runs: number
  confidence_level: number
  reliability_at_horizon: ProportionSummary
  ai: MetricSummary
  ao: MetricSummary
  mtbf_minutes: MetricSummary
  mttr_minutes: MetricSummary
  mtbm_minutes: MetricSummary
  mdt_minutes: MetricSummary
  downtime_minutes: MetricSummary
  production_loss: MetricSummary
  production_availability: MetricSummary
  repair_p90_minutes: number | null
  repair_p95_minutes: number | null
  maintainability_at_mttr: ProportionSummary | null
  failure_pareto: ParetoItem[]
  equipment: EquipmentAggregateMetrics[]
}

export interface SimulationResults {
  id: string
  status: string
  simulation_fingerprint: string
  model_hash: string
  scenario_hash: string
  configuration_hash: string
  software_version: string
  random_seed: number
  metrics: SystemAggregateMetrics
}

export interface SimulationEvent {
  id: string
  trial_run_id: number
  time_minutes: number
  event_type: string
  details: Record<string, unknown>
  equipment_id?: string | null
  failure_mode_id?: string | null
  task_id?: string | null
  resource_id?: string | null
  spare_part_id?: string | null
}

export interface SimulationEventsPage {
  items: SimulationEvent[]
  offset: number
  limit: number
  count: number
}

export interface PetriSourceMapping {
  kind: string
  role: string
  source_entity_type: string | null
  source_entity_id: string | null
  equipment_id: string | null
  failure_mode_id: string | null
  subnet_key: string | null
}

export interface PetriPlace {
  id: string
  role: string
  initial: number
  capacity: number | null
  source_entity_type: string | null
  source_entity_id: string | null
}

export interface PetriTransition {
  id: string
  role: string
  source_entity_type: string | null
  source_entity_id: string | null
}

export interface PetriArc {
  id: string
  source: string
  target: string
  weight: number
  arc_type: string | null
}

export interface PetriSubnet {
  key: string
  name: string
  case_id: string
  kind: string
  places: PetriPlace[]
  transitions: PetriTransition[]
  arcs: PetriArc[]
}

export interface PetriDefinition {
  version_id: string
  reliability_model_id: string | null
  reliability_model_hash: string
  schema_version: number
  subnets: PetriSubnet[]
  id_map: Record<string, PetriSourceMapping>
}

export interface PetriModel {
  id: string
  version_id: string
  reliability_model_id: string | null
  reliability_model_hash: string
  schema_version: string
  validation_status: string
  petri_pilot_version: string | null
  generated_at: string
  notes: string | null
  definition: PetriDefinition | null
}

export interface ReliabilityModel {
  id: string
  version_id: string
  model_hash: string
  validation_status: string
  generated_at: string
  notes: string | null
  snapshot?: Record<string, unknown> | null
}

export interface ValidationIssue {
  code: string
  message: string
  level: string
  severity: string
  entity: string | null
  entity_id: string | null
}

export interface ValidationReport {
  is_valid: boolean
  issues: ValidationIssue[]
}

export interface FailureMode {
  id: string
  equipment_id: string
  name: string
}

export interface ProductionImpact {
  id: string
  version_id: string
  equipment_id: string
  failure_mode_id: string | null
  loss_fraction: number
}

export interface MetricComparisonRow {
  metric: string
  baseline: number | null
  scenario: number | null
  delta: number | null
}

export interface ScenarioComparison {
  scenario_id: string
  scenario_version_id: string
  version_id: string
  baseline_run_id: string
  scenario_run_id: string
  baseline_scenario_hash: string
  scenario_scenario_hash: string
  rows: MetricComparisonRow[]
  deltas: Record<string, number | null>
}

export interface AnalystChatContext {
  system_id?: string | null
  version_id?: string | null
  scenario_id?: string | null
  simulation_run_id?: string | null
  equipment_id?: string | null
}

export interface AnalystReference {
  kind: string
  entity_id: string | null
  label: string
  detail: Record<string, unknown>
}

export interface AnalystToolCallRecord {
  name: string
  arguments: Record<string, unknown>
  ok: boolean
  result: Record<string, unknown>
  error: string | null
}

export interface AnalystChatResponse {
  answer: string
  references: AnalystReference[]
  tool_calls: AnalystToolCallRecord[]
  grounded: boolean
  model: string | null
}

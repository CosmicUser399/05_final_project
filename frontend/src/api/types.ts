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

import { apiDelete, apiGet, apiPatch, apiPost } from './client'
import type {
  CommitResult,
  Equipment,
  EquipmentConnection,
  GenerationJob,
  Proposal,
  Scenario,
  ScenarioChangeType,
  ScenarioComparison,
  SimulationStatus,
  System,
  SystemVersion,
} from './types'

export const systemsApi = {
  list: () => apiGet<System[]>('/systems'),
  get: (id: string) => apiGet<System>(`/systems/${id}`),
  create: (body: { name: string; description?: string }) =>
    apiPost<System>('/systems', body),
  update: (id: string, body: { name?: string; description?: string | null }) =>
    apiPatch<System>(`/systems/${id}`, body),
  remove: (id: string) => apiDelete(`/systems/${id}`),
  versions: (systemId: string) =>
    apiGet<SystemVersion[]>(`/systems/${systemId}/versions`),
}

export const equipmentApi = {
  list: (versionId: string) =>
    apiGet<Equipment[]>(`/versions/${versionId}/equipment`),
  create: (versionId: string, body: Record<string, unknown>) =>
    apiPost<Equipment>(`/versions/${versionId}/equipment`, body),
  update: (id: string, body: Record<string, unknown>) =>
    apiPatch<Equipment>(`/equipment/${id}`, body),
  remove: (id: string) => apiDelete(`/equipment/${id}`),
}

export const connectionsApi = {
  list: (versionId: string) =>
    apiGet<EquipmentConnection[]>(`/versions/${versionId}/connections`),
  create: (versionId: string, body: Record<string, unknown>) =>
    apiPost<EquipmentConnection>(
      `/versions/${versionId}/connections`,
      body,
    ),
  remove: (id: string) => apiDelete(`/connections/${id}`),
}

export const aiApi = {
  generateSystem: (body: {
    description: string
    provider: 'openai' | 'fabricate'
    process_inline?: boolean
  }) => apiPost<GenerationJob>('/ai/generate-system', body),
  getJob: (jobId: string) =>
    apiGet<GenerationJob>(`/ai/generation-jobs/${jobId}`),
  cancelJob: (jobId: string) =>
    apiPost<GenerationJob>(`/ai/generation-jobs/${jobId}/cancel`),
  getProposal: (proposalId: string) =>
    apiGet<Proposal>(`/ai/proposals/${proposalId}`),
  decideItem: (
    itemId: string,
    body: { decision: string; edited_payload?: Record<string, unknown> },
  ) => apiPost(`/ai/proposals/items/${itemId}/decide`, body),
  commitProposal: (
    proposalId: string,
    body: { system_name?: string; create_system?: boolean },
  ) => apiPost<CommitResult>(`/ai/proposals/${proposalId}/commit`, body),
}

export const scenariosApi = {
  list: (versionId: string) =>
    apiGet<Scenario[]>(`/versions/${versionId}/scenarios`),
  get: (scenarioId: string) =>
    apiGet<Scenario>(`/scenarios/${scenarioId}`),
  create: (
    versionId: string,
    body: {
      name: string
      description?: string
      changes: Array<{
        change_type: ScenarioChangeType
        target_lineage_id: string
        parameters: Record<string, unknown>
      }>
    },
  ) => apiPost<Scenario>(`/versions/${versionId}/scenarios`, body),
  addVersion: (
    scenarioId: string,
    body: {
      changes: Array<{
        change_type: ScenarioChangeType
        target_lineage_id: string
        parameters: Record<string, unknown>
      }>
    },
  ) =>
    apiPost<Scenario>(`/scenarios/${scenarioId}/versions`, body),
  simulate: (
    scenarioId: string,
    body: {
      horizon: number
      horizon_unit?: string
      number_of_runs?: number
      random_seed?: number
      parallel_runs?: number
    },
  ) =>
    apiPost<SimulationStatus>(
      `/scenarios/${scenarioId}/simulate`,
      body,
    ),
  compare: (
    scenarioId: string,
    params?: { baseline_run_id?: string; scenario_run_id?: string },
  ) => {
    const query = new URLSearchParams()
    if (params?.baseline_run_id) {
      query.set('baseline_run_id', params.baseline_run_id)
    }
    if (params?.scenario_run_id) {
      query.set('scenario_run_id', params.scenario_run_id)
    }
    const suffix = query.size > 0 ? `?${query.toString()}` : ''
    return apiGet<ScenarioComparison>(
      `/scenarios/${scenarioId}/compare${suffix}`,
    )
  },
}

export const simulationsApi = {
  create: (body: {
    version_id: string
    horizon: number
    horizon_unit?: string
    number_of_runs?: number
    random_seed?: number
    parallel_runs?: number
  }) => apiPost<SimulationStatus>('/simulations', body),
  get: (runId: string) =>
    apiGet<SimulationStatus>(`/simulations/${runId}`),
}

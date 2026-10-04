import {
  ApiError,
  apiDelete,
  apiGet,
  apiPatch,
  apiPost,
  apiPostWithHeaders,
} from './client'
import type {
  AnalystChatContext,
  AnalystChatResponse,
  CommitResult,
  Equipment,
  EquipmentConnection,
  FailureMode,
  GenerationJob,
  PetriModel,
  ProductionImpact,
  Proposal,
  ReferenceParameter,
  ReferenceSearchResult,
  ReferenceStatus,
  ReliabilityModel,
  Scenario,
  ScenarioChangeType,
  ScenarioComparison,
  SimulationEventsPage,
  SimulationResults,
  SimulationStatus,
  System,
  SystemVersion,
  TaxonomyNode,
  ValidationReport,
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

export const referenceApi = {
  status: () => apiGet<ReferenceStatus>('/reference/status'),
  ingest: (body: { replace?: boolean } = {}) =>
    apiPost<Record<string, unknown>>('/reference/ingest', body),
  searchParameters: (params: {
    query?: string
    equipment_class?: string
    equipment_class_code?: string
    parameter_kind?: string
    limit?: number
  }) => {
    const search = new URLSearchParams()
    if (params.query) search.set('query', params.query)
    if (params.equipment_class) {
      search.set('equipment_class', params.equipment_class)
    }
    if (params.equipment_class_code) {
      search.set('equipment_class_code', params.equipment_class_code)
    }
    if (params.parameter_kind) {
      search.set('parameter_kind', params.parameter_kind)
    }
    if (params.limit) search.set('limit', String(params.limit))
    const qs = search.toString()
    return apiGet<ReferenceSearchResult<ReferenceParameter>>(
      `/reference/parameters${qs ? `?${qs}` : ''}`,
    )
  },
  searchTaxonomy: (params: { query?: string; limit?: number }) => {
    const search = new URLSearchParams()
    if (params.query) search.set('query', params.query)
    if (params.limit) search.set('limit', String(params.limit))
    const qs = search.toString()
    return apiGet<ReferenceSearchResult<TaxonomyNode>>(
      `/reference/taxonomy${qs ? `?${qs}` : ''}`,
    )
  },
  suggest: (equipmentClass: string, limit = 20) =>
    apiGet<{ equipment_class: string; count: number; items: unknown[] }>(
      `/reference/suggest?equipment_class=${encodeURIComponent(equipmentClass)}&limit=${limit}`,
    ),
  linkEquipment: (
    equipmentId: string,
    body: { taxonomy_node_id: string; reason?: string },
  ) =>
    apiPost<Equipment>(
      `/reference/equipment/${equipmentId}/link`,
      body,
    ),
  applyParameter: (
    parameterId: string,
    body: { failure_mode_id: string; reason?: string },
  ) =>
    apiPost<Record<string, unknown>>(
      `/reference/parameters/${parameterId}/apply`,
      body,
    ),
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
  chat: (body: {
    message: string
    context?: AnalystChatContext
  }) => apiPost<AnalystChatResponse>('/ai/chat', body),
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
  list: (versionId: string) =>
    apiGet<SimulationStatus[]>(
      `/versions/${versionId}/simulations`,
    ),
  create: (
    body: {
      version_id: string
      horizon: number
      horizon_unit?: string
      number_of_runs?: number
      random_seed?: number
      parallel_runs?: number
      scenario_version_id?: string
    },
    idempotencyKey?: string,
  ) =>
    apiPostWithHeaders<SimulationStatus>(
      '/simulations',
      body,
      idempotencyKey
        ? { 'Idempotency-Key': idempotencyKey }
        : undefined,
    ),
  get: (runId: string) =>
    apiGet<SimulationStatus>(`/simulations/${runId}`),
  status: (runId: string) =>
    apiGet<SimulationStatus>(`/simulations/${runId}/status`),
  results: (runId: string) =>
    apiGet<SimulationResults>(`/simulations/${runId}/results`),
  events: (
    runId: string,
    params?: {
      offset?: number
      limit?: number
      event_type?: string
      equipment_id?: string
    },
  ) => {
    const query = new URLSearchParams()
    if (params?.offset !== undefined) {
      query.set('offset', String(params.offset))
    }
    if (params?.limit !== undefined) {
      query.set('limit', String(params.limit))
    }
    if (params?.event_type) {
      query.set('event_type', params.event_type)
    }
    if (params?.equipment_id) {
      query.set('equipment_id', params.equipment_id)
    }
    const suffix = query.size > 0 ? `?${query.toString()}` : ''
    return apiGet<SimulationEventsPage>(
      `/simulations/${runId}/events${suffix}`,
    )
  },
  cancel: (runId: string) =>
    apiPost<SimulationStatus>(`/simulations/${runId}/cancel`),
}

export const petriApi = {
  getLatest: (versionId: string) =>
    apiGet<PetriModel>(`/versions/${versionId}/petri`),
  generate: (versionId: string, notes?: string) =>
    apiPost<PetriModel>(`/versions/${versionId}/petri/generate`, {
      notes: notes ?? null,
    }),
  get: (petriId: string) =>
    apiGet<PetriModel>(`/petri/${petriId}`),
}

export const reliabilityApi = {
  getLatest: async (
    versionId: string,
  ): Promise<ReliabilityModel | null> => {
    try {
      return await apiGet<ReliabilityModel>(
        `/versions/${versionId}/reliability`,
      )
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        return null
      }
      throw error
    }
  },
  generate: (versionId: string, notes?: string) =>
    apiPost<ReliabilityModel>(
      `/versions/${versionId}/reliability/generate`,
      { notes: notes ?? null },
    ),
  validate: (versionId: string) =>
    apiPost<ValidationReport>(`/versions/${versionId}/validate`),
}

export const failureModesApi = {
  list: (equipmentId: string) =>
    apiGet<FailureMode[]>(
      `/equipment/${equipmentId}/failure-modes`,
    ),
  create: (equipmentId: string, body: Record<string, unknown>) =>
    apiPost<FailureMode>(
      `/equipment/${equipmentId}/failure-modes`,
      body,
    ),
}

export const maintenanceApi = {
  create: (equipmentId: string, body: Record<string, unknown>) =>
    apiPost(`/equipment/${equipmentId}/maintenance`, body),
}

export const productionApi = {
  listImpacts: (versionId: string) =>
    apiGet<ProductionImpact[]>(
      `/versions/${versionId}/production-impacts`,
    ),
  createImpact: (
    versionId: string,
    body: { equipment_id: string; loss_fraction: number },
  ) =>
    apiPost<ProductionImpact>(
      `/versions/${versionId}/production-impacts`,
      body,
    ),
}

import { apiDelete, apiGet, apiPatch, apiPost } from './client'
import type {
  CommitResult,
  Equipment,
  EquipmentConnection,
  GenerationJob,
  Proposal,
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

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { SimulationResults, SimulationStatus } from '../../api/types'
import { MetricsDashboard } from './MetricsDashboard'

const status: SimulationStatus = {
  id: '11111111-1111-1111-1111-111111111111',
  version_id: '22222222-2222-2222-2222-222222222222',
  scenario_version_id: null,
  status: 'COMPLETED',
  progress: 1,
  completed_runs: 10,
  total_runs: 10,
  random_seed: 42,
  model_hash: 'a'.repeat(64),
  scenario_hash: 'b'.repeat(64),
  configuration_hash: 'c'.repeat(64),
  software_version: '0.1.0',
  simulation_fingerprint: 'd'.repeat(64),
  error_message: null,
}

const results: SimulationResults = {
  id: status.id,
  status: 'COMPLETED',
  simulation_fingerprint: status.simulation_fingerprint,
  model_hash: status.model_hash,
  scenario_hash: status.scenario_hash,
  configuration_hash: status.configuration_hash,
  software_version: status.software_version,
  random_seed: 42,
  metrics: {
    number_of_runs: 10,
    completed_runs: 10,
    confidence_level: 0.95,
    reliability_at_horizon: {
      value: 0.8,
      successes: 8,
      trials: 10,
      ci_low: 0.5,
      ci_high: 0.95,
      method: 'wilson',
    },
    ai: {
      mean: 0.99,
      median: 0.99,
      p5: 0.97,
      p50: 0.99,
      p95: 1,
      ci_low: 0.98,
      ci_high: 1,
      sample_size: 10,
    },
    ao: {
      mean: 0.98,
      median: 0.98,
      p5: 0.96,
      p50: 0.98,
      p95: 0.99,
      ci_low: 0.97,
      ci_high: 0.99,
      sample_size: 10,
    },
    mtbf_minutes: {
      mean: 1000,
      median: 1000,
      p5: 800,
      p50: 1000,
      p95: 1200,
      ci_low: 900,
      ci_high: 1100,
      sample_size: 10,
    },
    mttr_minutes: {
      mean: 10,
      median: 10,
      p5: 8,
      p50: 10,
      p95: 12,
      ci_low: 9,
      ci_high: 11,
      sample_size: 10,
    },
    mtbm_minutes: {
      mean: 500,
      median: 500,
      p5: 400,
      p50: 500,
      p95: 600,
      ci_low: 450,
      ci_high: 550,
      sample_size: 10,
    },
    mdt_minutes: {
      mean: 20,
      median: 20,
      p5: 15,
      p50: 20,
      p95: 25,
      ci_low: 18,
      ci_high: 22,
      sample_size: 10,
    },
    downtime_minutes: {
      mean: 30,
      median: 30,
      p5: 20,
      p50: 30,
      p95: 40,
      ci_low: 25,
      ci_high: 35,
      sample_size: 10,
    },
    production_loss: {
      mean: 1,
      median: 1,
      p5: 0,
      p50: 1,
      p95: 2,
      ci_low: 0.5,
      ci_high: 1.5,
      sample_size: 10,
    },
    production_availability: {
      mean: 0.97,
      median: 0.97,
      p5: 0.95,
      p50: 0.97,
      p95: 0.99,
      ci_low: 0.96,
      ci_high: 0.98,
      sample_size: 10,
    },
    repair_p90_minutes: 12,
    repair_p95_minutes: 14,
    maintainability_at_mttr: null,
    failure_pareto: [],
    equipment: [],
  },
}

describe('MetricsDashboard', () => {
  it('renders aggregate rows and provenance', () => {
    render(<MetricsDashboard status={status} results={results} />)

    expect(
      screen.getByRole('heading', { name: 'Дашборд метрик' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Ai')).toBeInTheDocument()
    expect(screen.getByText(/seed=42/)).toBeInTheDocument()
    expect(screen.getByText(/R\(horizon\)/)).toBeInTheDocument()
  })
})

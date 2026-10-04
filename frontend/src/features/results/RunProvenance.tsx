import { Stack, Typography } from '@mui/material'

import type { SimulationResults, SimulationStatus } from '../../api/types'
import { shortHash } from './format'

interface Props {
  status: SimulationStatus
  results?: SimulationResults | null
}

export function RunProvenance({ status, results }: Props) {
  const seed = results?.random_seed ?? status.random_seed
  const modelHash = results?.model_hash ?? status.model_hash
  const scenarioHash = results?.scenario_hash ?? status.scenario_hash
  const configHash =
    results?.configuration_hash ?? status.configuration_hash
  const fingerprint =
    results?.simulation_fingerprint ?? status.simulation_fingerprint
  const software =
    results?.software_version ?? status.software_version

  return (
    <Stack spacing={0.5}>
      <Typography variant="caption" color="text.secondary">
        simulation: {status.id}
      </Typography>
      <Typography variant="caption" color="text.secondary">
        version: {status.version_id}
        {status.scenario_version_id
          ? `; scenario_version: ${status.scenario_version_id}`
          : '; scenario: baseline'}
      </Typography>
      <Typography variant="caption" color="text.secondary">
        seed={seed}; model_hash={shortHash(modelHash)}; scenario_hash=
        {shortHash(scenarioHash)}; configuration_hash=
        {shortHash(configHash)}
      </Typography>
      <Typography variant="caption" color="text.secondary">
        fingerprint={shortHash(fingerprint)}; software={software}
      </Typography>
    </Stack>
  )
}

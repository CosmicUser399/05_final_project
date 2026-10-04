import { useEffect, useState } from 'react'

import type { SimulationStatus } from '../../api/types'

const TERMINAL = new Set(['COMPLETED', 'FAILED', 'CANCELLED'])

/**
 * Subscribe to SSE progress for a simulation run.
 *
 * Falls back to no-op when EventSource is unavailable.
 */
export function useSimulationStream(
  runId: string | null,
  enabled: boolean,
): SimulationStatus | null {
  const [status, setStatus] = useState<SimulationStatus | null>(null)

  useEffect(() => {
    if (!runId || !enabled) {
      return
    }
    if (typeof EventSource === 'undefined') {
      return
    }
    const source = new EventSource(`/api/v1/simulations/${runId}/stream`)

    const onProgress = (event: MessageEvent<string>) => {
      try {
        const payload = JSON.parse(event.data) as SimulationStatus
        setStatus(payload)
        if (TERMINAL.has(payload.status)) {
          source.close()
        }
      } catch {
        // Ignore malformed SSE payloads.
      }
    }

    source.addEventListener('progress', onProgress as EventListener)
    source.addEventListener('done', onProgress as EventListener)
    source.onerror = () => {
      source.close()
    }

    return () => {
      source.close()
    }
  }, [runId, enabled])

  return status
}

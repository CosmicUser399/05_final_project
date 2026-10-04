import {
  equipmentApi,
  failureModesApi,
  maintenanceApi,
  productionApi,
  reliabilityApi,
} from '../../api/resources'
import type { ReliabilityModel } from '../../api/types'

const USER_PROVENANCE = {
  source_type: 'USER_DEFINED',
  confidence: 'MEDIUM',
}

/**
 * Fill missing failure modes / CM / production impacts, then compile.
 *
 * Backend rejects simulation without a reliability snapshot; AI
 * equipment often lacks modes/impacts needed for compile.
 */
export async function prepareAndCompileReliability(
  versionId: string,
): Promise<ReliabilityModel> {
  const equipment = await equipmentApi.list(versionId)
  const impacts = await productionApi.listImpacts(versionId)
  const covered = new Set(impacts.map((item) => item.equipment_id))

  for (const item of equipment) {
    const modes = await failureModesApi.list(item.id)
    let modeId = modes[0]?.id
    if (!modeId) {
      const created = await failureModesApi.create(item.id, {
        name: `Default failure (${item.tag})`,
        is_detectable: true,
        pf_interval: { value: 14, unit: 'DAYS' },
        distribution: {
          distribution: {
            type: 'WEIBULL',
            shape: 2.0,
            scale: 1000.0,
            unit: 'DAYS',
          },
          provenance: USER_PROVENANCE,
        },
      })
      modeId = created.id
      await maintenanceApi.create(item.id, {
        name: `Corrective repair (${item.tag})`,
        task_type: 'CORRECTIVE',
        trigger: 'ON_FAILURE',
        failure_mode_id: modeId,
        duration: {
          distribution: {
            type: 'CONSTANT',
            value: 10.0,
            unit: 'HOURS',
          },
          provenance: USER_PROVENANCE,
        },
      })
    }

    const needsImpact =
      item.criticality === 'CRITICAL' || item.criticality === 'HIGH'
    if (needsImpact && !covered.has(item.id)) {
      await productionApi.createImpact(versionId, {
        equipment_id: item.id,
        loss_fraction: 1.0,
      })
      covered.add(item.id)
    }
  }

  return reliabilityApi.generate(
    versionId,
    'compiled from UI prepare step',
  )
}

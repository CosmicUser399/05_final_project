import { reliabilityApi } from '../../api/resources'
import type { ReliabilityModel } from '../../api/types'

/**
 * Fill missing failure modes / CM / production impacts, then compile.
 *
 * Backend owns the enrichment: AI drafts often lack PF intervals and
 * distributions; the prepare endpoint completes them for compile.
 */
export async function prepareAndCompileReliability(
  versionId: string,
): Promise<ReliabilityModel> {
  return reliabilityApi.prepare(versionId, 'compiled from UI prepare step')
}

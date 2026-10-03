/**
 * Fetch OpenAPI JSON from a running backend and write a summary stamp.
 * Hand-maintained typed client lives in src/api/*; this script documents
 * the contract refresh workflow for P7-07.
 */
import { writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const base = process.env.OPENAPI_URL ?? 'http://127.0.0.1:8000/openapi.json'

const response = await fetch(base)
if (!response.ok) {
  console.error(`Failed to fetch OpenAPI from ${base}: ${response.status}`)
  process.exit(1)
}
const spec = await response.json()
const out = resolve(import.meta.dirname, '../src/api/openapi.stamp.json')
writeFileSync(
  out,
  JSON.stringify(
    {
      fetched_at: new Date().toISOString(),
      title: spec.info?.title ?? null,
      version: spec.info?.version ?? null,
      path_count: Object.keys(spec.paths ?? {}).length,
      source: base,
    },
    null,
    2,
  ),
)
console.log(`Wrote OpenAPI stamp to ${out}`)

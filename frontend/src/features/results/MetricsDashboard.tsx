import {
  Box,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'

import type {
  MetricSummary,
  ProportionSummary,
  SimulationResults,
  SimulationStatus,
  SystemAggregateMetrics,
} from '../../api/types'
import { formatNum, formatPct } from './format'
import { RunProvenance } from './RunProvenance'

interface Props {
  status: SimulationStatus
  results: SimulationResults
}

interface MetricRow {
  key: string
  label: string
  unit: string
  kind: 'metric' | 'proportion' | 'scalar'
  summary?: MetricSummary
  proportion?: ProportionSummary
  scalar?: number | null
}

function rowsFromMetrics(metrics: SystemAggregateMetrics): MetricRow[] {
  return [
    {
      key: 'reliability',
      label: 'R(horizon)',
      unit: 'доля',
      kind: 'proportion',
      proportion: metrics.reliability_at_horizon,
    },
    {
      key: 'ai',
      label: 'Ai',
      unit: 'доля',
      kind: 'metric',
      summary: metrics.ai,
    },
    {
      key: 'ao',
      label: 'Ao',
      unit: 'доля',
      kind: 'metric',
      summary: metrics.ao,
    },
    {
      key: 'mtbf',
      label: 'MTBF',
      unit: 'мин',
      kind: 'metric',
      summary: metrics.mtbf_minutes,
    },
    {
      key: 'mttr',
      label: 'MTTR',
      unit: 'мин',
      kind: 'metric',
      summary: metrics.mttr_minutes,
    },
    {
      key: 'mtbm',
      label: 'MTBM',
      unit: 'мин',
      kind: 'metric',
      summary: metrics.mtbm_minutes,
    },
    {
      key: 'mdt',
      label: 'MDT',
      unit: 'мин',
      kind: 'metric',
      summary: metrics.mdt_minutes,
    },
    {
      key: 'downtime',
      label: 'Downtime',
      unit: 'мин',
      kind: 'metric',
      summary: metrics.downtime_minutes,
    },
    {
      key: 'loss',
      label: 'Production Loss',
      unit: 'ед.',
      kind: 'metric',
      summary: metrics.production_loss,
    },
    {
      key: 'pa',
      label: 'Production Availability',
      unit: 'доля',
      kind: 'metric',
      summary: metrics.production_availability,
    },
    {
      key: 'repair_p90',
      label: 'Repair p90',
      unit: 'мин',
      kind: 'scalar',
      scalar: metrics.repair_p90_minutes,
    },
    {
      key: 'repair_p95',
      label: 'Repair p95',
      unit: 'мин',
      kind: 'scalar',
      scalar: metrics.repair_p95_minutes,
    },
  ]
}

function renderMean(row: MetricRow): string {
  if (row.kind === 'proportion') {
    return formatPct(row.proportion?.value)
  }
  if (row.kind === 'scalar') {
    return formatNum(row.scalar)
  }
  return formatNum(row.summary?.mean)
}

function renderMedian(row: MetricRow): string {
  if (row.kind !== 'metric') {
    return '—'
  }
  return formatNum(row.summary?.median ?? row.summary?.p50)
}

function renderP5(row: MetricRow): string {
  if (row.kind !== 'metric') {
    return '—'
  }
  return formatNum(row.summary?.p5)
}

function renderP95(row: MetricRow): string {
  if (row.kind !== 'metric') {
    return '—'
  }
  return formatNum(row.summary?.p95)
}

function renderCi(row: MetricRow): string {
  if (row.kind === 'proportion') {
    const low = row.proportion?.ci_low
    const high = row.proportion?.ci_high
    if (low === null || low === undefined) {
      return '—'
    }
    return `${formatPct(low)} … ${formatPct(high)}`
  }
  if (row.kind === 'metric') {
    const low = row.summary?.ci_low
    const high = row.summary?.ci_high
    if (low === null || low === undefined) {
      return '—'
    }
    return `${formatNum(low)} … ${formatNum(high)}`
  }
  return '—'
}

export function MetricsDashboard({ status, results }: Props) {
  const metrics = results.metrics
  const rows = rowsFromMetrics(metrics)

  return (
    <Stack spacing={2}>
      <Typography variant="h6">Дашборд метрик</Typography>
      <Typography variant="body2" color="text.secondary">
        Прогоны: {metrics.completed_runs}/{metrics.number_of_runs}; CI{' '}
        {formatPct(metrics.confidence_level)}
      </Typography>
      <RunProvenance status={status} results={results} />
      <Box sx={{ overflowX: 'auto' }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Метрика</TableCell>
              <TableCell>Ед.</TableCell>
              <TableCell>Mean / Value</TableCell>
              <TableCell>Median</TableCell>
              <TableCell>P5</TableCell>
              <TableCell>P95</TableCell>
              <TableCell>CI</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.key}>
                <TableCell>{row.label}</TableCell>
                <TableCell>{row.unit}</TableCell>
                <TableCell>{renderMean(row)}</TableCell>
                <TableCell>{renderMedian(row)}</TableCell>
                <TableCell>{renderP5(row)}</TableCell>
                <TableCell>{renderP95(row)}</TableCell>
                <TableCell>{renderCi(row)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>
    </Stack>
  )
}

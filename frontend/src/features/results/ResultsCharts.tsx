import { Alert, Box, Stack, Typography } from '@mui/material'
import ReactECharts from 'echarts-for-react'

import type {
  MetricSummary,
  SimulationResults,
  SimulationStatus,
} from '../../api/types'
import { formatNum, formatPct } from './format'
import { RunProvenance } from './RunProvenance'

interface Props {
  status: SimulationStatus
  results: SimulationResults
}

function quantileSeries(
  label: string,
  summary: MetricSummary | undefined,
): {
  name: string
  p5: number | null
  median: number | null
  p95: number | null
  mean: number | null
} {
  return {
    name: label,
    p5: summary?.p5 ?? null,
    median: summary?.median ?? summary?.p50 ?? null,
    p95: summary?.p95 ?? null,
    mean: summary?.mean ?? null,
  }
}

export function ResultsCharts({ status, results }: Props) {
  const metrics = results.metrics
  const reliability = metrics.reliability_at_horizon
  const distributions = [
    quantileSeries('Ai', metrics.ai),
    quantileSeries('Ao', metrics.ao),
    quantileSeries('Downtime', metrics.downtime_minutes),
    quantileSeries('MTBF', metrics.mtbf_minutes),
    quantileSeries('MTTR', metrics.mttr_minutes),
    quantileSeries('Production Loss', metrics.production_loss),
  ]

  const distributionOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['P5', 'Median', 'Mean', 'P95'] },
    grid: { left: 56, right: 24, top: 40, bottom: 64 },
    xAxis: {
      type: 'category',
      data: distributions.map((item) => item.name),
      axisLabel: { interval: 0, rotate: 18 },
    },
    yAxis: { type: 'value' },
    series: [
      {
        name: 'P5',
        type: 'bar',
        data: distributions.map((item) => item.p5),
        itemStyle: { color: '#8a9aab' },
      },
      {
        name: 'Median',
        type: 'bar',
        data: distributions.map((item) => item.median),
        itemStyle: { color: '#3d5a73' },
      },
      {
        name: 'Mean',
        type: 'bar',
        data: distributions.map((item) => item.mean),
        itemStyle: { color: '#2f6f4e' },
      },
      {
        name: 'P95',
        type: 'bar',
        data: distributions.map((item) => item.p95),
        itemStyle: { color: '#b35c1e' },
      },
    ],
  }

  const pareto = metrics.failure_pareto ?? []
  const paretoOption = {
    tooltip: { trigger: 'axis' },
    grid: { left: 48, right: 48, top: 32, bottom: 80 },
    xAxis: {
      type: 'category',
      data: pareto.map((item) => item.key.slice(0, 10)),
      axisLabel: { rotate: 30, interval: 0 },
    },
    yAxis: [
      { type: 'value', name: 'Count' },
      { type: 'value', name: 'Share', max: 1 },
    ],
    series: [
      {
        name: 'Count',
        type: 'bar',
        data: pareto.map((item) => item.count),
        itemStyle: { color: '#5b6b7c' },
      },
      {
        name: 'Share',
        type: 'line',
        yAxisIndex: 1,
        data: pareto.map((item) => item.share),
        itemStyle: { color: '#2f6f4e' },
      },
    ],
  }

  const equipment = metrics.equipment ?? []
  const loadOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['PM', 'CM', 'Detections'] },
    grid: { left: 48, right: 24, top: 40, bottom: 64 },
    xAxis: {
      type: 'category',
      data: equipment.map((item) => item.equipment_id.slice(0, 8)),
      axisLabel: { rotate: 30, interval: 0 },
    },
    yAxis: { type: 'value', name: 'mean count' },
    series: [
      {
        name: 'PM',
        type: 'bar',
        stack: 'maint',
        data: equipment.map((item) => item.pm_count.mean),
        itemStyle: { color: '#3d5a73' },
      },
      {
        name: 'CM',
        type: 'bar',
        stack: 'maint',
        data: equipment.map((item) => item.cm_count.mean),
        itemStyle: { color: '#b35c1e' },
      },
      {
        name: 'Detections',
        type: 'bar',
        stack: 'maint',
        data: equipment.map((item) => item.detection_count.mean),
        itemStyle: { color: '#2f6f4e' },
      },
    ],
  }

  return (
    <Stack spacing={3}>
      <Typography variant="h6">Графики</Typography>
      <RunProvenance status={status} results={results} />

      <Box>
        <Typography variant="subtitle1" gutterBottom>
          Reliability at horizon
        </Typography>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          Кривая R(t) по времени в MVP не персистится; показывается
          backend-значение R(horizon) с CI.
        </Typography>
        <Typography variant="h5">
          {formatPct(reliability.value)}{' '}
          <Typography component="span" variant="body2" color="text.secondary">
            CI {formatPct(reliability.ci_low)} …{' '}
            {formatPct(reliability.ci_high)} ({reliability.method});{' '}
            {reliability.successes}/{reliability.trials}
          </Typography>
        </Typography>
      </Box>

      <Box>
        <Typography variant="subtitle1" gutterBottom>
          Распределения (квантили по прогонам)
        </Typography>
        <ReactECharts option={distributionOption} style={{ height: 360 }} />
      </Box>

      <Box>
        <Typography variant="subtitle1" gutterBottom>
          Pareto отказов
        </Typography>
        {pareto.length === 0 ? (
          <Alert severity="info">Нет данных Pareto</Alert>
        ) : (
          <ReactECharts option={paretoOption} style={{ height: 360 }} />
        )}
        <Typography variant="caption" color="text.secondary">
          key = failure_mode / equipment id с backend; share уже посчитан на
          сервере.
        </Typography>
      </Box>

      <Box>
        <Typography variant="subtitle1" gutterBottom>
          Нагрузка ТО / диагностики (mean по оборудованию)
        </Typography>
        {equipment.length === 0 ? (
          <Alert severity="info">Нет equipment metrics</Alert>
        ) : (
          <ReactECharts option={loadOption} style={{ height: 360 }} />
        )}
        <Typography variant="caption" color="text.secondary">
          Потребление запчастей смотрите в Event explorer (типы SPARE_*).
          Агрегаты spare Pareto в MVP не считаются.
        </Typography>
      </Box>

      <Typography variant="body2" color="text.secondary">
        Repair p90={formatNum(metrics.repair_p90_minutes)} мин; p95=
        {formatNum(metrics.repair_p95_minutes)} мин
      </Typography>
    </Stack>
  )
}

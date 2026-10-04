import { Box, Typography } from '@mui/material'
import ReactECharts from 'echarts-for-react'

import type { MetricComparisonRow } from '../../api/types'

const CHART_METRICS = [
  'availability',
  'production_loss',
  'downtime_minutes',
  'mtbf_minutes',
  'mttr_minutes',
] as const

const LABELS: Record<string, string> = {
  availability: 'Availability (Ai)',
  production_loss: 'Production Loss',
  downtime_minutes: 'Downtime, мин',
  mtbf_minutes: 'MTBF, мин',
  mttr_minutes: 'MTTR, мин',
}

interface CompareChartProps {
  rows: MetricComparisonRow[]
}

export function CompareChart({ rows }: CompareChartProps) {
  const selected = CHART_METRICS.map((key) =>
    rows.find((row) => row.metric === key),
  ).filter((row): row is MetricComparisonRow => Boolean(row))

  if (selected.length === 0) {
    return null
  }

  const categories = selected.map((row) => LABELS[row.metric] ?? row.metric)
  const option = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['Baseline', 'Scenario'] },
    grid: { left: 48, right: 24, top: 40, bottom: 48 },
    xAxis: {
      type: 'category',
      data: categories,
      axisLabel: { interval: 0, rotate: 20 },
    },
    yAxis: { type: 'value' },
    series: [
      {
        name: 'Baseline',
        type: 'bar',
        data: selected.map((row) => row.baseline),
        itemStyle: { color: '#5b6b7c' },
      },
      {
        name: 'Scenario',
        type: 'bar',
        data: selected.map((row) => row.scenario),
        itemStyle: { color: '#2f6f4e' },
      },
    ],
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Сравнение метрик
      </Typography>
      <ReactECharts option={option} style={{ height: 360 }} />
    </Box>
  )
}

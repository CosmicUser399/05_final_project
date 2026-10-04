import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { DataGrid, type GridColDef } from '@mui/x-data-grid'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link as RouterLink, useParams } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { scenariosApi, simulationsApi } from '../../api/resources'
import type {
  MetricComparisonRow,
  ScenarioComparison,
  SimulationStatus,
} from '../../api/types'
import { CompareChart } from './CompareChart'

const METRIC_LABELS: Record<string, string> = {
  availability: 'Availability (Ai)',
  operational_availability: 'Operational Availability (Ao)',
  mtbf_minutes: 'MTBF, мин',
  mttr_minutes: 'MTTR, мин',
  downtime_minutes: 'Downtime, мин',
  production_loss: 'Production Loss',
  production_availability: 'Production Availability',
  pm_count: 'PM Count',
  cm_count: 'CM Count',
  diagnostic_count: 'Diagnostic Count',
  maintenance_cost: 'Maintenance Cost',
  spare_cost: 'Spare Cost',
}

function formatNum(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '—'
  }
  return Number.isFinite(value) ? value.toPrecision(4) : '—'
}

const compareColumns: GridColDef<MetricComparisonRow>[] = [
  {
    field: 'metric',
    headerName: 'Метрика',
    flex: 1.2,
    minWidth: 180,
    valueGetter: (_value, row) =>
      METRIC_LABELS[row.metric] ?? row.metric,
  },
  {
    field: 'baseline',
    headerName: 'Baseline',
    flex: 1,
    valueFormatter: (value: number | null) => formatNum(value),
  },
  {
    field: 'scenario',
    headerName: 'Scenario',
    flex: 1,
    valueFormatter: (value: number | null) => formatNum(value),
  },
  {
    field: 'delta',
    headerName: 'Δ',
    flex: 1,
    valueFormatter: (value: number | null) => formatNum(value),
  },
]

export function ScenarioDetailPage() {
  const { scenarioId = '' } = useParams()
  const [horizon, setHorizon] = useState('365')
  const [runs, setRuns] = useState('20')
  const [seed, setSeed] = useState('42')
  const [job, setJob] = useState<SimulationStatus | null>(null)
  const [comparison, setComparison] = useState<ScenarioComparison | null>(
    null,
  )
  const [error, setError] = useState<string | null>(null)

  const scenarioQuery = useQuery({
    queryKey: ['scenario', scenarioId],
    queryFn: () => scenariosApi.get(scenarioId),
    enabled: Boolean(scenarioId),
  })

  const simulateMutation = useMutation({
    mutationFn: () =>
      scenariosApi.simulate(scenarioId, {
        horizon: Number(horizon),
        horizon_unit: 'DAYS',
        number_of_runs: Number(runs),
        random_seed: Number(seed),
        parallel_runs: 1,
      }),
    onSuccess: (created) => {
      setJob(created)
      setComparison(null)
      setError(null)
    },
    onError: (err: unknown) => {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Не удалось запустить симуляцию',
      )
    },
  })

  const compareMutation = useMutation({
    mutationFn: () => scenariosApi.compare(scenarioId),
    onSuccess: (result) => {
      setComparison(result)
      setError(null)
    },
    onError: (err: unknown) => {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Нет завершённых прогонов для сравнения',
      )
    },
  })

  useEffect(() => {
    if (!job) {
      return
    }
    if (
      job.status === 'COMPLETED' ||
      job.status === 'FAILED' ||
      job.status === 'CANCELLED'
    ) {
      return
    }
    const timer = window.setInterval(async () => {
      try {
        const next = await simulationsApi.get(job.id)
        setJob(next)
      } catch (err) {
        setError(
          err instanceof ApiError ? err.message : 'Ошибка статуса',
        )
      }
    }, 1000)
    return () => window.clearInterval(timer)
  }, [job])

  if (scenarioQuery.isLoading) {
    return <CircularProgress />
  }
  if (scenarioQuery.isError || !scenarioQuery.data) {
    return <Alert severity="error">Сценарий не найден</Alert>
  }

  const scenario = scenarioQuery.data
  const changes = scenario.current_version?.changes ?? []

  return (
    <Stack spacing={2}>
      <Button
        component={RouterLink}
        to="/scenarios"
        size="small"
        sx={{ alignSelf: 'flex-start' }}
      >
        ← К списку сценариев
      </Button>
      <Typography variant="h4">{scenario.name}</Typography>
      <Typography color="text.secondary">
        {scenario.description || 'Без описания'}
      </Typography>
      <Typography variant="body2">
        Версия системы: {scenario.version_id}
      </Typography>
      <Typography variant="body2">
        scenario_hash:{' '}
        {scenario.current_version?.scenario_hash ?? '—'}
      </Typography>

      <Typography variant="h6">Изменения (overlay)</Typography>
      {changes.length === 0 ? (
        <Alert severity="info">Нет изменений</Alert>
      ) : (
        <Stack spacing={1}>
          {changes.map((change) => (
            <Box
              key={change.id}
              sx={{
                borderBottom: '1px solid',
                borderColor: 'divider',
                py: 1,
              }}
            >
              <Typography variant="subtitle2">
                {change.change_type}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                lineage: {change.target_lineage_id}
              </Typography>
              <Typography variant="body2" component="pre">
                {JSON.stringify(change.parameters, null, 2)}
              </Typography>
            </Box>
          ))}
        </Stack>
      )}

      <Typography variant="h6">Симуляция сценария</Typography>
      <Stack direction={{ xs: 'column', md: 'row' }} spacing={1}>
        <TextField
          label="Горизонт, суток"
          size="small"
          value={horizon}
          onChange={(event) => setHorizon(event.target.value)}
        />
        <TextField
          label="Число прогонов"
          size="small"
          value={runs}
          onChange={(event) => setRuns(event.target.value)}
        />
        <TextField
          label="Seed"
          size="small"
          value={seed}
          onChange={(event) => setSeed(event.target.value)}
        />
        <Button
          variant="contained"
          onClick={() => simulateMutation.mutate()}
          disabled={simulateMutation.isPending}
        >
          Запустить
        </Button>
        <Button
          variant="outlined"
          onClick={() => compareMutation.mutate()}
          disabled={compareMutation.isPending}
        >
          Сравнить с baseline
        </Button>
      </Stack>

      {job ? (
        <Alert
          severity={
            job.status === 'COMPLETED'
              ? 'success'
              : job.status === 'FAILED'
                ? 'error'
                : 'info'
          }
          action={
            <Button
              component={RouterLink}
              to={`/simulations/${job.id}`}
              color="inherit"
              size="small"
            >
              Результаты
            </Button>
          }
        >
          Симуляция {job.id}: {job.status} (
          {job.completed_runs}/{job.total_runs}), seed={job.random_seed}
        </Alert>
      ) : null}

      {error ? <Alert severity="error">{error}</Alert> : null}

      {comparison ? (
        <Stack spacing={2}>
          <Typography variant="body2">
            Δ Availability:{' '}
            {formatNum(comparison.deltas.availability)}; Δ Production
            Loss: {formatNum(comparison.deltas.production_loss)}; Δ
            Maintenance Cost:{' '}
            {formatNum(comparison.deltas.maintenance_cost)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            baseline run {comparison.baseline_run_id}; scenario run{' '}
            {comparison.scenario_run_id}; seed/fingerprint на backend
          </Typography>
          <DataGrid
            rows={comparison.rows.map((row) => ({
              ...row,
              id: row.metric,
            }))}
            columns={compareColumns}
            autoHeight
            hideFooter
            disableRowSelectionOnClick
          />
          <CompareChart rows={comparison.rows} />
        </Stack>
      ) : null}
    </Stack>
  )
}

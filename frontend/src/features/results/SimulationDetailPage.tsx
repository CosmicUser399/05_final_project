import {
  Alert,
  Button,
  CircularProgress,
  LinearProgress,
  Stack,
  Tab,
  Tabs,
  Typography,
} from '@mui/material'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link as RouterLink, useParams } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { simulationsApi } from '../../api/resources'
import { EquipmentMetricsTable } from './EquipmentMetricsTable'
import { EventExplorer } from './EventExplorer'
import { MetricDefinitionsPanel } from './MetricDefinitionsPanel'
import { MetricsDashboard } from './MetricsDashboard'
import { PetriViewer } from './PetriViewer'
import { ResultsCharts } from './ResultsCharts'
import { RunProvenance } from './RunProvenance'
import { useSimulationStream } from './useSimulationStream'

const TERMINAL = new Set(['COMPLETED', 'FAILED', 'CANCELLED'])

export function SimulationDetailPage() {
  const { runId = '' } = useParams()
  const [tab, setTab] = useState(0)
  const queryClient = useQueryClient()

  const statusQuery = useQuery({
    queryKey: ['simulation', runId],
    queryFn: () => simulationsApi.get(runId),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (!status || TERMINAL.has(status)) {
        return false
      }
      return 2000
    },
  })

  const status = statusQuery.data ?? null
  const streaming = Boolean(status && !TERMINAL.has(status.status))
  const streamStatus = useSimulationStream(runId, streaming)
  const effectiveStatus = streamStatus ?? status

  const resultsQuery = useQuery({
    queryKey: ['simulation-results', runId],
    queryFn: () => simulationsApi.results(runId),
    enabled: effectiveStatus?.status === 'COMPLETED',
  })

  const cancelMutation = useMutation({
    mutationFn: () => simulationsApi.cancel(runId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ['simulation', runId],
      })
    },
  })

  if (statusQuery.isLoading) {
    return <CircularProgress />
  }
  if (statusQuery.isError || !effectiveStatus) {
    return <Alert severity="error">Симуляция не найдена</Alert>
  }

  const completed = effectiveStatus.status === 'COMPLETED'
  const results = resultsQuery.data ?? null

  return (
    <Stack spacing={2}>
      <Button
        component={RouterLink}
        to="/simulations"
        size="small"
        sx={{ alignSelf: 'flex-start' }}
      >
        ← К списку симуляций
      </Button>
      <Typography variant="h4">Результаты симуляции</Typography>
      <RunProvenance status={effectiveStatus} results={results} />
      <Typography variant="body2">
        Статус: {effectiveStatus.status}; прогоны{' '}
        {effectiveStatus.completed_runs}/{effectiveStatus.total_runs}
      </Typography>
      {!TERMINAL.has(effectiveStatus.status) ? (
        <Stack spacing={1}>
          <LinearProgress
            variant="determinate"
            value={Math.round(effectiveStatus.progress * 100)}
          />
          <Button
            size="small"
            color="warning"
            variant="outlined"
            disabled={cancelMutation.isPending}
            onClick={() => cancelMutation.mutate()}
            sx={{ alignSelf: 'flex-start' }}
          >
            Отменить
          </Button>
        </Stack>
      ) : null}
      {effectiveStatus.error_message ? (
        <Alert severity="error">{effectiveStatus.error_message}</Alert>
      ) : null}
      {resultsQuery.isError ? (
        <Alert severity="error">
          {resultsQuery.error instanceof ApiError
            ? resultsQuery.error.message
            : 'Результаты недоступны'}
        </Alert>
      ) : null}

      <Tabs
        value={tab}
        onChange={(_, value: number) => setTab(value)}
        variant="scrollable"
        scrollButtons="auto"
      >
        <Tab label="Дашборд" />
        <Tab label="Графики" />
        <Tab label="Оборудование" />
        <Tab label="События" />
        <Tab label="Определения" />
        <Tab label="Petri" />
      </Tabs>

      {tab === 0 ? (
        completed && results ? (
          <MetricsDashboard status={effectiveStatus} results={results} />
        ) : (
          <Alert severity="info">
            Дашборд доступен после завершения (COMPLETED).
          </Alert>
        )
      ) : null}

      {tab === 1 ? (
        completed && results ? (
          <ResultsCharts status={effectiveStatus} results={results} />
        ) : (
          <Alert severity="info">Графики доступны после завершения.</Alert>
        )
      ) : null}

      {tab === 2 ? (
        completed && results ? (
          <EquipmentMetricsTable status={effectiveStatus} results={results} />
        ) : (
          <Alert severity="info">
            Метрики оборудования доступны после завершения.
          </Alert>
        )
      ) : null}

      {tab === 3 ? <EventExplorer status={effectiveStatus} /> : null}

      {tab === 4 ? <MetricDefinitionsPanel /> : null}

      {tab === 5 ? (
        <PetriViewer versionId={effectiveStatus.version_id} />
      ) : null}
    </Stack>
  )
}

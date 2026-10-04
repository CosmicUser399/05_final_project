import {
  Alert,
  Button,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { DataGrid, type GridColDef } from '@mui/x-data-grid'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'

import { ApiError } from '../../api/client'
import {
  reliabilityApi,
  simulationsApi,
  systemsApi,
} from '../../api/resources'
import type { SimulationStatus } from '../../api/types'
import { ReliabilityPanel } from '../reliability/ReliabilityPanel'
import { shortHash } from './format'
import { useSimulationStream } from './useSimulationStream'

const columns: GridColDef<SimulationStatus>[] = [
  {
    field: 'id',
    headerName: 'Run',
    flex: 1.2,
    minWidth: 220,
    renderCell: (params) => (
      <Button
        component={RouterLink}
        to={`/simulations/${params.row.id}`}
        size="small"
      >
        {String(params.value).slice(0, 8)}…
      </Button>
    ),
  },
  { field: 'status', headerName: 'Статус', width: 130 },
  {
    field: 'progress',
    headerName: 'Прогресс',
    width: 110,
    valueFormatter: (value: number) =>
      `${Math.round((value ?? 0) * 100)} %`,
  },
  {
    field: 'completed_runs',
    headerName: 'Прогоны',
    width: 120,
    valueGetter: (_value, row) =>
      `${row.completed_runs}/${row.total_runs}`,
  },
  {
    field: 'random_seed',
    headerName: 'Seed',
    width: 90,
  },
  {
    field: 'scenario_version_id',
    headerName: 'Scenario',
    width: 120,
    valueGetter: (_value, row) =>
      row.scenario_version_id ? 'overlay' : 'baseline',
  },
  {
    field: 'model_hash',
    headerName: 'model_hash',
    flex: 1,
    valueGetter: (_value, row) => shortHash(row.model_hash),
  },
  {
    field: 'created_at',
    headerName: 'Создано',
    width: 190,
  },
]

export function SimulationsListPage() {
  const queryClient = useQueryClient()
  const [systemId, setSystemId] = useState('')
  const [versionId, setVersionId] = useState('')
  const [horizon, setHorizon] = useState('365')
  const [runs, setRuns] = useState('20')
  const [seed, setSeed] = useState('42')
  const [error, setError] = useState<string | null>(null)
  const [activeRunId, setActiveRunId] = useState<string | null>(null)

  const systemsQuery = useQuery({
    queryKey: ['systems'],
    queryFn: systemsApi.list,
  })

  const versionsQuery = useQuery({
    queryKey: ['versions', systemId],
    queryFn: () => systemsApi.versions(systemId),
    enabled: Boolean(systemId),
  })

  const selectedVersionId = useMemo(() => {
    if (versionId) {
      return versionId
    }
    const versions = versionsQuery.data ?? []
    if (versions.length === 0) {
      return ''
    }
    const latest = [...versions].sort(
      (a, b) => b.version_number - a.version_number,
    )[0]
    return latest?.id ?? ''
  }, [versionId, versionsQuery.data])

  const simulationsQuery = useQuery({
    queryKey: ['simulations', selectedVersionId],
    queryFn: () => simulationsApi.list(selectedVersionId),
    enabled: Boolean(selectedVersionId),
    refetchInterval: (query) => {
      const rows = query.state.data ?? []
      const busy = rows.some(
        (row) =>
          row.status !== 'COMPLETED' &&
          row.status !== 'FAILED' &&
          row.status !== 'CANCELLED',
      )
      return busy ? 2000 : false
    },
  })

  const reliabilityQuery = useQuery({
    queryKey: ['reliability', selectedVersionId],
    queryFn: () => reliabilityApi.getLatest(selectedVersionId),
    enabled: Boolean(selectedVersionId),
    retry: false,
  })

  const streamStatus = useSimulationStream(
    activeRunId,
    Boolean(activeRunId),
  )

  useEffect(() => {
    if (
      !streamStatus ||
      (streamStatus.status !== 'COMPLETED' &&
        streamStatus.status !== 'FAILED' &&
        streamStatus.status !== 'CANCELLED')
    ) {
      return
    }
    void queryClient.invalidateQueries({
      queryKey: ['simulations', selectedVersionId],
    })
  }, [streamStatus, queryClient, selectedVersionId])

  const createMutation = useMutation({
    mutationFn: () =>
      simulationsApi.create({
        version_id: selectedVersionId,
        horizon: Number(horizon),
        horizon_unit: 'DAYS',
        number_of_runs: Number(runs),
        random_seed: Number(seed),
        parallel_runs: 1,
      }),
    onSuccess: (created) => {
      setError(null)
      setActiveRunId(created.id)
      void queryClient.invalidateQueries({
        queryKey: ['simulations', selectedVersionId],
      })
    },
    onError: (err: unknown) => {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Не удалось запустить симуляцию',
      )
    },
  })

  const modelReady = Boolean(reliabilityQuery.data)

  return (
    <Stack spacing={2}>
      <Typography variant="h4">Симуляции</Typography>
      <Typography color="text.secondary">
        Запуск Monte Carlo, прогресс (SSE) и переход к дашборду
        результатов. Расчёты только на backend.
      </Typography>

      <Stack direction={{ xs: 'column', md: 'row' }} spacing={1}>
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel id="system">Система</InputLabel>
          <Select
            labelId="system"
            label="Система"
            value={systemId}
            onChange={(event) => {
              setSystemId(event.target.value)
              setVersionId('')
            }}
          >
            {(systemsQuery.data ?? []).map((system) => (
              <MenuItem key={system.id} value={system.id}>
                {system.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl
          size="small"
          sx={{ minWidth: 220 }}
          disabled={!systemId}
        >
          <InputLabel id="version">Версия</InputLabel>
          <Select
            labelId="version"
            label="Версия"
            value={selectedVersionId}
            onChange={(event) => setVersionId(event.target.value)}
          >
            {(versionsQuery.data ?? []).map((version) => (
              <MenuItem key={version.id} value={version.id}>
                v{version.version_number} ({version.status})
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Stack>

      {selectedVersionId ? (
        <ReliabilityPanel versionId={selectedVersionId} />
      ) : null}

      <Stack direction={{ xs: 'column', md: 'row' }} spacing={1}>
        <TextField
          size="small"
          label="Горизонт, суток"
          value={horizon}
          onChange={(event) => setHorizon(event.target.value)}
        />
        <TextField
          size="small"
          label="Число прогонов"
          value={runs}
          onChange={(event) => setRuns(event.target.value)}
        />
        <TextField
          size="small"
          label="Seed"
          value={seed}
          onChange={(event) => setSeed(event.target.value)}
        />
        <Button
          variant="contained"
          disabled={
            !selectedVersionId ||
            !modelReady ||
            createMutation.isPending
          }
          onClick={() => createMutation.mutate()}
        >
          Запустить baseline
        </Button>
      </Stack>
      {selectedVersionId && !modelReady ? (
        <Alert severity="info">
          Сначала скомпилируйте Reliability Model (кнопка выше), затем
          запускайте baseline.
        </Alert>
      ) : null}

      {streamStatus ? (
        <Alert severity="info">
          SSE: {streamStatus.id.slice(0, 8)}… — {streamStatus.status}{' '}
          ({streamStatus.completed_runs}/{streamStatus.total_runs})
        </Alert>
      ) : null}
      {error ? <Alert severity="error">{error}</Alert> : null}

      {!selectedVersionId ? (
        <Alert severity="info">
          Выберите систему и версию, чтобы увидеть запуски.
        </Alert>
      ) : simulationsQuery.isError ? (
        <Alert severity="error">Не удалось загрузить симуляции</Alert>
      ) : (
        <DataGrid
          rows={simulationsQuery.data ?? []}
          columns={columns}
          loading={simulationsQuery.isFetching}
          autoHeight
          pageSizeOptions={[10, 25]}
          initialState={{
            pagination: { paginationModel: { pageSize: 10 } },
          }}
          disableRowSelectionOnClick
        />
      )}
    </Stack>
  )
}

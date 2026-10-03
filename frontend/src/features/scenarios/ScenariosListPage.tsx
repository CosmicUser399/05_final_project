import {
  Alert,
  Box,
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
import { useMemo, useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { scenariosApi, systemsApi } from '../../api/resources'
import type { Scenario, ScenarioChangeType } from '../../api/types'

const CHANGE_TYPES: ScenarioChangeType[] = [
  'CHANGE_DIAGNOSTIC_INTERVAL',
  'CHANGE_DETECTION_PROBABILITY',
  'CHANGE_PM_INTERVAL',
  'CHANGE_MAINTENANCE_DISTRIBUTION',
  'CHANGE_RESOURCE',
  'CHANGE_SPARE_STOCK',
  'CHANGE_FAILURE_PARAMETER',
  'ENABLE_TASK',
  'DISABLE_TASK',
]

const columns: GridColDef<Scenario>[] = [
  {
    field: 'name',
    headerName: 'Название',
    flex: 1,
    minWidth: 180,
    renderCell: (params) => (
      <Button
        component={RouterLink}
        to={`/scenarios/${params.row.id}`}
        size="small"
      >
        {params.value}
      </Button>
    ),
  },
  {
    field: 'description',
    headerName: 'Описание',
    flex: 1.2,
    minWidth: 200,
  },
  {
    field: 'scenario_hash',
    headerName: 'scenario_hash',
    flex: 1,
    minWidth: 160,
    valueGetter: (_value, row) =>
      row.current_version?.scenario_hash?.slice(0, 12) ?? '—',
  },
  { field: 'created_at', headerName: 'Создано', width: 200 },
]

export function ScenariosListPage() {
  const queryClient = useQueryClient()
  const [systemId, setSystemId] = useState('')
  const [versionId, setVersionId] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [changeType, setChangeType] =
    useState<ScenarioChangeType>('CHANGE_DIAGNOSTIC_INTERVAL')
  const [targetLineageId, setTargetLineageId] = useState('')
  const [paramValue, setParamValue] = useState('14')
  const [paramUnit, setParamUnit] = useState('DAYS')
  const [error, setError] = useState<string | null>(null)

  const systemsQuery = useQuery({
    queryKey: ['systems'],
    queryFn: systemsApi.list,
  })

  const versionsQuery = useQuery({
    queryKey: ['versions', systemId],
    queryFn: () => systemsApi.versions(systemId),
    enabled: Boolean(systemId),
  })

  const scenariosQuery = useQuery({
    queryKey: ['scenarios', versionId],
    queryFn: () => scenariosApi.list(versionId),
    enabled: Boolean(versionId),
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

  const createMutation = useMutation({
    mutationFn: () => {
      const parameters =
        changeType === 'CHANGE_DETECTION_PROBABILITY'
          ? { detection_probability: Number(paramValue) }
          : changeType === 'DISABLE_TASK' ||
              changeType === 'ENABLE_TASK'
            ? {}
            : { value: Number(paramValue), unit: paramUnit }
      return scenariosApi.create(selectedVersionId, {
        name,
        description: description || undefined,
        changes: [
          {
            change_type: changeType,
            target_lineage_id: targetLineageId,
            parameters,
          },
        ],
      })
    },
    onSuccess: async () => {
      setName('')
      setDescription('')
      setError(null)
      await queryClient.invalidateQueries({
        queryKey: ['scenarios', selectedVersionId],
      })
    },
    onError: (err: unknown) => {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Не удалось создать сценарий',
      )
    },
  })

  return (
    <Stack spacing={2}>
      <Typography variant="h4">Сценарии</Typography>
      <Typography color="text.secondary">
        Overlay поверх замороженной версии: baseline не меняется.
        Сравнение Availability, Production Loss и других метрик.
      </Typography>

      <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel id="system-label">Система</InputLabel>
          <Select
            labelId="system-label"
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
        <FormControl size="small" sx={{ minWidth: 260 }} disabled={!systemId}>
          <InputLabel id="version-label">Версия</InputLabel>
          <Select
            labelId="version-label"
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
        <Box
          component="form"
          onSubmit={(event) => {
            event.preventDefault()
            createMutation.mutate()
          }}
          sx={{
            display: 'grid',
            gap: 1,
            gridTemplateColumns: {
              xs: '1fr',
              md: '1fr 1fr',
            },
          }}
        >
          <TextField
            label="Название сценария"
            size="small"
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <TextField
            label="Описание"
            size="small"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
          <FormControl size="small">
            <InputLabel id="change-type-label">Тип изменения</InputLabel>
            <Select
              labelId="change-type-label"
              label="Тип изменения"
              value={changeType}
              onChange={(event) =>
                setChangeType(event.target.value as ScenarioChangeType)
              }
            >
              {CHANGE_TYPES.map((type) => (
                <MenuItem key={type} value={type}>
                  {type}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="target_lineage_id"
            size="small"
            required
            value={targetLineageId}
            onChange={(event) => setTargetLineageId(event.target.value)}
            helperText="UUID lineage целевой сущности"
          />
          <TextField
            label="Значение / вероятность"
            size="small"
            value={paramValue}
            onChange={(event) => setParamValue(event.target.value)}
          />
          <TextField
            label="Единица"
            size="small"
            value={paramUnit}
            onChange={(event) => setParamUnit(event.target.value)}
            disabled={
              changeType === 'CHANGE_DETECTION_PROBABILITY' ||
              changeType === 'DISABLE_TASK' ||
              changeType === 'ENABLE_TASK'
            }
          />
          <Box sx={{ gridColumn: '1 / -1' }}>
            <Button
              type="submit"
              variant="contained"
              disabled={createMutation.isPending || !name}
            >
              Создать сценарий
            </Button>
          </Box>
        </Box>
      ) : (
        <Alert severity="info">
          Выберите систему и версию с скомпилированной моделью
          надёжности.
        </Alert>
      )}

      {error ? <Alert severity="error">{error}</Alert> : null}

      {selectedVersionId ? (
        <DataGrid
          rows={scenariosQuery.data ?? []}
          columns={columns}
          loading={scenariosQuery.isLoading}
          autoHeight
          disableRowSelectionOnClick
          pageSizeOptions={[10, 25]}
          initialState={{
            pagination: { paginationModel: { pageSize: 10 } },
          }}
        />
      ) : null}
    </Stack>
  )
}

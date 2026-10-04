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
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { simulationsApi } from '../../api/resources'
import type { SimulationEvent, SimulationStatus } from '../../api/types'
import { formatNum } from './format'
import { RunProvenance } from './RunProvenance'

interface Props {
  status: SimulationStatus
}

const PAGE_SIZE = 50

const EVENT_TYPES = [
  '',
  'FAILURE',
  'POTENTIAL_FAILURE',
  'PM_START',
  'PM_COMPLETE',
  'CM_START',
  'CM_COMPLETE',
  'DIAGNOSTIC',
  'DETECTION',
  'PRODUCTION_CHANGE',
  'RESOURCE_BUSY',
  'RESOURCE_AVAILABLE',
  'SPARE_REQUEST',
  'SPARE_AVAILABLE',
]

const columns: GridColDef<SimulationEvent>[] = [
  { field: 'trial_run_id', headerName: 'Trial', width: 80 },
  {
    field: 'time_minutes',
    headerName: 't, мин',
    width: 110,
    valueFormatter: (value: number) => formatNum(value, 6),
  },
  { field: 'event_type', headerName: 'Тип', width: 160 },
  {
    field: 'equipment_id',
    headerName: 'Equipment',
    flex: 1,
    minWidth: 180,
    valueGetter: (_value, row) => row.equipment_id ?? '—',
  },
  {
    field: 'failure_mode_id',
    headerName: 'Failure mode',
    flex: 1,
    minWidth: 160,
    valueGetter: (_value, row) => row.failure_mode_id ?? '—',
  },
  {
    field: 'details',
    headerName: 'Details',
    flex: 1.4,
    minWidth: 200,
    valueGetter: (_value, row) => JSON.stringify(row.details ?? {}),
  },
]

export function EventExplorer({ status }: Props) {
  const [offset, setOffset] = useState(0)
  const [eventType, setEventType] = useState('')
  const [equipmentId, setEquipmentId] = useState('')

  const eventsQuery = useQuery({
    queryKey: [
      'simulation-events',
      status.id,
      offset,
      eventType,
      equipmentId,
    ],
    queryFn: () =>
      simulationsApi.events(status.id, {
        offset,
        limit: PAGE_SIZE,
        event_type: eventType || undefined,
        equipment_id: equipmentId.trim() || undefined,
      }),
  })

  const page = eventsQuery.data
  const hasNext = (page?.count ?? 0) >= PAGE_SIZE
  const hasPrev = offset > 0

  return (
    <Stack spacing={2}>
      <Typography variant="h6">Event explorer</Typography>
      <Typography variant="body2" color="text.secondary">
        Серверная пагинация и фильтры. Полный лог пишется только для
        ограниченного числа прогонов (backend).
      </Typography>
      <RunProvenance status={status} />
      <Stack direction={{ xs: 'column', md: 'row' }} spacing={1}>
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel id="event-type">Тип события</InputLabel>
          <Select
            labelId="event-type"
            label="Тип события"
            value={eventType}
            onChange={(event) => {
              setEventType(event.target.value)
              setOffset(0)
            }}
          >
            <MenuItem value="">Все</MenuItem>
            {EVENT_TYPES.filter(Boolean).map((type) => (
              <MenuItem key={type} value={type}>
                {type}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <TextField
          size="small"
          label="equipment_id"
          value={equipmentId}
          onChange={(event) => {
            setEquipmentId(event.target.value)
            setOffset(0)
          }}
          sx={{ minWidth: 280 }}
        />
        <Button
          size="small"
          disabled={!hasPrev || eventsQuery.isFetching}
          onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
        >
          ← Назад
        </Button>
        <Button
          size="small"
          disabled={!hasNext || eventsQuery.isFetching}
          onClick={() => setOffset((value) => value + PAGE_SIZE)}
        >
          Вперёд →
        </Button>
        <Typography variant="body2" sx={{ alignSelf: 'center' }}>
          offset={offset}; page={page?.count ?? 0}
        </Typography>
      </Stack>
      {eventsQuery.isError ? (
        <Alert severity="error">Не удалось загрузить события</Alert>
      ) : null}
      <DataGrid
        rows={page?.items ?? []}
        columns={columns}
        getRowId={(row) => row.id}
        loading={eventsQuery.isFetching}
        autoHeight
        hideFooter
        disableRowSelectionOnClick
      />
    </Stack>
  )
}

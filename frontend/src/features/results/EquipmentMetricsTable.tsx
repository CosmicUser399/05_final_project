import { Stack, Typography } from '@mui/material'
import { DataGrid, type GridColDef } from '@mui/x-data-grid'

import type {
  EquipmentAggregateMetrics,
  SimulationResults,
  SimulationStatus,
} from '../../api/types'
import { formatNum } from './format'
import { RunProvenance } from './RunProvenance'

interface Props {
  status: SimulationStatus
  results: SimulationResults
}

function meanOf(
  row: EquipmentAggregateMetrics,
  field: keyof EquipmentAggregateMetrics,
): number | null {
  const value = row[field]
  if (
    typeof value === 'object' &&
    value !== null &&
    'mean' in value
  ) {
    return value.mean
  }
  return null
}

const columns: GridColDef<EquipmentAggregateMetrics>[] = [
  {
    field: 'equipment_id',
    headerName: 'Equipment',
    flex: 1.2,
    minWidth: 220,
  },
  {
    field: 'ai',
    headerName: 'Ai mean',
    flex: 0.8,
    valueGetter: (_value, row) => formatNum(meanOf(row, 'ai')),
  },
  {
    field: 'mtbf_minutes',
    headerName: 'MTBF mean, мин',
    flex: 1,
    valueGetter: (_value, row) =>
      formatNum(meanOf(row, 'mtbf_minutes')),
  },
  {
    field: 'mttr_minutes',
    headerName: 'MTTR mean, мин',
    flex: 1,
    valueGetter: (_value, row) =>
      formatNum(meanOf(row, 'mttr_minutes')),
  },
  {
    field: 'downtime_minutes',
    headerName: 'Downtime mean, мин',
    flex: 1,
    valueGetter: (_value, row) =>
      formatNum(meanOf(row, 'downtime_minutes')),
  },
  {
    field: 'failure_count',
    headerName: 'Failures mean',
    flex: 0.9,
    valueGetter: (_value, row) =>
      formatNum(meanOf(row, 'failure_count')),
  },
  {
    field: 'pm_count',
    headerName: 'PM mean',
    flex: 0.7,
    valueGetter: (_value, row) => formatNum(meanOf(row, 'pm_count')),
  },
  {
    field: 'cm_count',
    headerName: 'CM mean',
    flex: 0.7,
    valueGetter: (_value, row) => formatNum(meanOf(row, 'cm_count')),
  },
]

export function EquipmentMetricsTable({ status, results }: Props) {
  const rows = results.metrics.equipment ?? []

  return (
    <Stack spacing={2}>
      <Typography variant="h6">Метрики оборудования</Typography>
      <RunProvenance status={status} results={results} />
      <DataGrid
        rows={rows.map((row) => ({
          ...row,
          id: row.equipment_id,
        }))}
        columns={columns}
        autoHeight
        pageSizeOptions={[10, 25, 50]}
        initialState={{
          pagination: { paginationModel: { pageSize: 10 } },
        }}
        disableRowSelectionOnClick
      />
    </Stack>
  )
}

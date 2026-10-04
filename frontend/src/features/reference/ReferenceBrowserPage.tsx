import {
  Alert,
  Box,
  Button,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material'
import { DataGrid, type GridColDef } from '@mui/x-data-grid'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { ApiError } from '../../api/client'
import { referenceApi } from '../../api/resources'
import type { ReferenceParameter, TaxonomyNode } from '../../api/types'
import { ProvenanceBadge } from '../../components/ProvenanceBadge'
import { ProvenancePanel } from '../../components/ProvenancePanel'

const parameterColumns: GridColDef<ReferenceParameter>[] = [
  {
    field: 'equipment_class',
    headerName: 'Класс',
    flex: 1,
    minWidth: 140,
  },
  {
    field: 'equipment_class_code',
    headerName: 'Код',
    width: 120,
  },
  {
    field: 'failure_mode_name',
    headerName: 'Failure mode',
    flex: 1,
    minWidth: 140,
  },
  {
    field: 'parameter_name',
    headerName: 'Параметр',
    width: 140,
  },
  {
    field: 'value',
    headerName: 'Значение',
    width: 110,
    valueGetter: (_value, row) => `${row.value} ${row.unit}`,
  },
  {
    field: 'source_type',
    headerName: 'Источник',
    width: 160,
    renderCell: (params) => (
      <ProvenanceBadge
        sourceType={params.row.source_type}
        confidence={params.row.confidence}
      />
    ),
  },
  {
    field: 'source_reference',
    headerName: 'Ссылка',
    flex: 1.2,
    minWidth: 180,
  },
]

const taxonomyColumns: GridColDef<TaxonomyNode>[] = [
  { field: 'code', headerName: 'Код ISO', width: 140 },
  { field: 'name', headerName: 'Название', flex: 1, minWidth: 180 },
  {
    field: 'parent_id',
    headerName: 'parent_id',
    flex: 1,
    minWidth: 160,
    valueGetter: (_value, row) => row.parent_id?.slice(0, 8) ?? '—',
  },
]

export function ReferenceBrowserPage() {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState(0)
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<ReferenceParameter | null>(null)
  const [error, setError] = useState<string | null>(null)

  const statusQuery = useQuery({
    queryKey: ['reference', 'status'],
    queryFn: referenceApi.status,
  })

  const parametersQuery = useQuery({
    queryKey: ['reference', 'parameters', query],
    queryFn: () =>
      referenceApi.searchParameters({
        query: query.trim() || undefined,
        limit: 100,
      }),
    enabled: tab === 0,
  })

  const taxonomyQuery = useQuery({
    queryKey: ['reference', 'taxonomy', query],
    queryFn: () =>
      referenceApi.searchTaxonomy({
        query: query.trim() || undefined,
        limit: 100,
      }),
    enabled: tab === 1,
  })

  const ingestMutation = useMutation({
    mutationFn: () => referenceApi.ingest({ replace: false }),
    onSuccess: async () => {
      setError(null)
      await queryClient.invalidateQueries({ queryKey: ['reference'] })
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err.message : 'Ошибка загрузки')
    },
  })

  const parameterRows = useMemo(
    () => parametersQuery.data?.items ?? [],
    [parametersQuery.data],
  )
  const taxonomyRows = useMemo(
    () => taxonomyQuery.data?.items ?? [],
    [taxonomyQuery.data],
  )

  const available = statusQuery.data?.available ?? false

  return (
    <Stack spacing={2}>
      <Typography variant="h4">Справочник OREDA / ISO 14224</Typography>
      <Typography color="text.secondary">
        Курируемые demo-извлечения для тестирования ПО. PDF handbook не
        распространяются; полуавтоматическая загрузка — CSV/JSON после ручной
        проверки.
      </Typography>
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
        <Button
          variant="contained"
          disabled={ingestMutation.isPending}
          onClick={() => ingestMutation.mutate()}
        >
          Загрузить demo-справочник
        </Button>
        <Typography variant="body2" color="text.secondary">
          OREDA: {statusQuery.data?.oreda_parameters ?? 0}; ISO nodes:{' '}
          {statusQuery.data?.iso_taxonomy_nodes ?? 0}
          {available ? '' : ' (пусто)'}
        </Typography>
      </Stack>
      {error ? <Alert severity="error">{error}</Alert> : null}
      {!available ? (
        <Alert severity="info">
          Справочник ещё не загружен. Нажмите «Загрузить demo-справочник».
        </Alert>
      ) : null}
      <TextField
        label="Поиск"
        size="small"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        sx={{ maxWidth: 360 }}
      />
      <Tabs value={tab} onChange={(_, value: number) => setTab(value)}>
        <Tab label="Параметры OREDA" />
        <Tab label="Таксономия ISO 14224" />
      </Tabs>
      {tab === 0 ? (
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
          <Box sx={{ height: 480, flex: 2, width: '100%' }}>
            <DataGrid
              rows={parameterRows}
              columns={parameterColumns}
              loading={parametersQuery.isLoading}
              disableRowSelectionOnClick
              onRowClick={(params) =>
                setSelected(params.row as ReferenceParameter)
              }
              pageSizeOptions={[25, 50, 100]}
              initialState={{
                pagination: { paginationModel: { pageSize: 25 } },
              }}
            />
          </Box>
          <Box sx={{ flex: 1, minWidth: 260 }}>
            <Typography variant="h6" gutterBottom>
              Provenance
            </Typography>
            {selected ? (
              <ProvenancePanel
                value={selected.value}
                unit={selected.unit}
                sourceType={selected.source_type}
                sourceDocument={selected.source_document}
                sourceReference={selected.source_reference}
                confidence={selected.confidence}
              />
            ) : (
              <Typography color="text.secondary" variant="body2">
                Выберите строку, чтобы увидеть значение, источник, ссылку и
                уверенность.
              </Typography>
            )}
          </Box>
        </Stack>
      ) : (
        <Box sx={{ height: 480, width: '100%' }}>
          <DataGrid
            rows={taxonomyRows}
            columns={taxonomyColumns}
            loading={taxonomyQuery.isLoading}
            disableRowSelectionOnClick
            pageSizeOptions={[25, 50, 100]}
            initialState={{
              pagination: { paginationModel: { pageSize: 25 } },
            }}
          />
        </Box>
      )}
    </Stack>
  )
}

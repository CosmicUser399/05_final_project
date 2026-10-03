import { Alert, Box, Button, Stack, TextField } from '@mui/material'
import {
  DataGrid,
  type GridColDef,
  type GridRowModel,
} from '@mui/x-data-grid'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { ApiError } from '../../api/client'
import { equipmentApi } from '../../api/resources'

interface Props {
  versionId: string
}

export function EquipmentTable({ versionId }: Props) {
  const queryClient = useQueryClient()
  const [tag, setTag] = useState('')
  const [name, setName] = useState('')
  const [filter, setFilter] = useState('')
  const [error, setError] = useState<string | null>(null)

  const query = useQuery({
    queryKey: ['equipment', versionId],
    queryFn: () => equipmentApi.list(versionId),
  })

  const createMutation = useMutation({
    mutationFn: () =>
      equipmentApi.create(versionId, { tag, name, quantity: 1 }),
    onSuccess: async () => {
      setTag('')
      setName('')
      setError(null)
      await queryClient.invalidateQueries({ queryKey: ['equipment', versionId] })
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err.message : 'Ошибка создания')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      equipmentApi.update(id, body),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['equipment', versionId] })
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err.message : 'Ошибка обновления')
    },
  })

  const rows = useMemo(() => {
    const data = query.data ?? []
    const q = filter.trim().toLowerCase()
    if (!q) {
      return data
    }
    return data.filter(
      (row) =>
        row.tag.toLowerCase().includes(q) ||
        row.name.toLowerCase().includes(q) ||
        (row.category ?? '').toLowerCase().includes(q),
    )
  }, [filter, query.data])

  const columns: GridColDef[] = [
    { field: 'tag', headerName: 'Тег', width: 120, editable: true },
    {
      field: 'name',
      headerName: 'Название',
      flex: 1,
      minWidth: 160,
      editable: true,
    },
    { field: 'category', headerName: 'Категория', width: 130, editable: true },
    {
      field: 'equipment_class',
      headerName: 'Класс',
      width: 130,
      editable: true,
    },
    {
      field: 'criticality',
      headerName: 'Критичность',
      width: 130,
      editable: true,
    },
    {
      field: 'quantity',
      headerName: 'Кол-во',
      width: 90,
      type: 'number',
      editable: true,
    },
  ]

  const processRowUpdate = async (newRow: GridRowModel, oldRow: GridRowModel) => {
    const changed: Record<string, unknown> = {}
    for (const key of [
      'tag',
      'name',
      'category',
      'equipment_class',
      'criticality',
      'quantity',
    ] as const) {
      if (newRow[key] !== oldRow[key]) {
        changed[key] = newRow[key]
      }
    }
    if (Object.keys(changed).length > 0) {
      await updateMutation.mutateAsync({ id: String(newRow.id), body: changed })
    }
    return newRow
  }

  return (
    <Stack spacing={2}>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        <TextField
          size="small"
          label="Поиск"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
        />
        <TextField
          size="small"
          label="Тег"
          value={tag}
          onChange={(event) => setTag(event.target.value)}
        />
        <TextField
          size="small"
          label="Название"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <Button
          variant="contained"
          disabled={!tag.trim() || !name.trim()}
          onClick={() => createMutation.mutate()}
        >
          Добавить
        </Button>
      </Box>
      {error ? <Alert severity="error">{error}</Alert> : null}
      <Box sx={{ height: 440, width: '100%' }}>
        <DataGrid
          rows={rows}
          columns={columns}
          loading={query.isLoading}
          processRowUpdate={processRowUpdate}
          onProcessRowUpdateError={(err) => {
            setError(err instanceof Error ? err.message : 'Ошибка строки')
          }}
          disableRowSelectionOnClick
          pageSizeOptions={[10, 25, 50]}
          initialState={{
            pagination: { paginationModel: { pageSize: 10 } },
          }}
        />
      </Box>
    </Stack>
  )
}

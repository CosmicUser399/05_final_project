import {
  Alert,
  Box,
  Button,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { DataGrid, type GridColDef } from '@mui/x-data-grid'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { systemsApi } from '../../api/resources'
import type { System } from '../../api/types'

const columns: GridColDef<System>[] = [
  {
    field: 'name',
    headerName: 'Название',
    flex: 1,
    minWidth: 180,
    renderCell: (params) => (
      <Button
        component={RouterLink}
        to={`/systems/${params.row.id}`}
        size="small"
      >
        {params.value}
      </Button>
    ),
  },
  { field: 'description', headerName: 'Описание', flex: 1.5, minWidth: 220 },
  { field: 'created_at', headerName: 'Создано', width: 200 },
]

export function SystemsListPage() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)

  const systemsQuery = useQuery({
    queryKey: ['systems'],
    queryFn: systemsApi.list,
  })

  const createMutation = useMutation({
    mutationFn: () => systemsApi.create({ name, description: description || undefined }),
    onSuccess: async () => {
      setName('')
      setDescription('')
      setError(null)
      await queryClient.invalidateQueries({ queryKey: ['systems'] })
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err.message : 'Не удалось создать')
    },
  })

  return (
    <Stack spacing={2}>
      <Typography variant="h4">Системы</Typography>
      <Box
        component="form"
        onSubmit={(event) => {
          event.preventDefault()
          createMutation.mutate()
        }}
        sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}
      >
        <TextField
          label="Название"
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
          sx={{ minWidth: 280 }}
        />
        <Button type="submit" variant="contained" disabled={!name.trim()}>
          Создать
        </Button>
        <Button component={RouterLink} to="/ai/generate" variant="outlined">
          AI-генерация
        </Button>
      </Box>
      {error ? <Alert severity="error">{error}</Alert> : null}
      {systemsQuery.isError ? (
        <Alert severity="error">Не удалось загрузить системы</Alert>
      ) : null}
      <Box sx={{ height: 420, width: '100%' }}>
        <DataGrid
          rows={systemsQuery.data ?? []}
          columns={columns}
          loading={systemsQuery.isLoading}
          disableRowSelectionOnClick
          pageSizeOptions={[10, 25]}
          initialState={{
            pagination: { paginationModel: { pageSize: 10 } },
          }}
        />
      </Box>
    </Stack>
  )
}

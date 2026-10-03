import {
  Alert,
  Box,
  Button,
  Stack,
  Typography,
} from '@mui/material'
import { DataGrid, type GridColDef } from '@mui/x-data-grid'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { aiApi } from '../../api/resources'
import type { ProposalItem } from '../../api/types'
import { ProvenanceBadge } from '../../components/ProvenanceBadge'

export function ProposalReviewPage() {
  const { proposalId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)

  const proposalQuery = useQuery({
    queryKey: ['proposal', proposalId],
    queryFn: () => aiApi.getProposal(proposalId),
    enabled: Boolean(proposalId),
  })

  const decideMutation = useMutation({
    mutationFn: ({
      itemId,
      decision,
    }: {
      itemId: string
      decision: string
    }) => aiApi.decideItem(itemId, { decision }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['proposal', proposalId] })
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err.message : 'Ошибка решения')
    },
  })

  const commitMutation = useMutation({
    mutationFn: () =>
      aiApi.commitProposal(proposalId, {
        system_name: proposalQuery.data?.title,
        create_system: true,
      }),
    onSuccess: (result) => {
      navigate(`/systems/${result.system_id}`)
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err.message : 'Ошибка commit')
    },
  })

  const rows = proposalQuery.data?.items ?? []
  const acceptedCount = rows.filter((item) =>
    ['ACCEPTED', 'EDITED'].includes(item.decision),
  ).length

  const columns: GridColDef<ProposalItem>[] = useMemo(
    () => [
      { field: 'item_type', headerName: 'Тип', width: 140 },
      { field: 'item_key', headerName: 'Ключ', flex: 1, minWidth: 160 },
      {
        field: 'payload',
        headerName: 'Содержимое',
        flex: 1.5,
        minWidth: 220,
        valueGetter: (_value, row) => JSON.stringify(row.payload),
      },
      { field: 'decision', headerName: 'Решение', width: 120 },
      {
        field: 'actions',
        headerName: 'Действия',
        width: 260,
        sortable: false,
        renderCell: (params) => (
          <Box sx={{ display: 'flex', gap: 0.5 }}>
            <Button
              size="small"
              onClick={() =>
                decideMutation.mutate({
                  itemId: params.row.id,
                  decision: 'ACCEPTED',
                })
              }
            >
              Принять
            </Button>
            <Button
              size="small"
              color="inherit"
              onClick={() =>
                decideMutation.mutate({
                  itemId: params.row.id,
                  decision: 'REJECTED',
                })
              }
            >
              Отклонить
            </Button>
          </Box>
        ),
      },
    ],
    [decideMutation],
  )

  if (proposalQuery.isError) {
    return <Alert severity="error">Предложение не найдено</Alert>
  }

  const provenance = proposalQuery.data?.provenance ?? {}

  return (
    <Stack spacing={2}>
      <Typography variant="h4">
        {proposalQuery.data?.title ?? 'Ревью предложения'}
      </Typography>
      <Stack direction="row" spacing={1} alignItems="center">
        <Typography variant="body2">
          Провайдер: {proposalQuery.data?.provider}
        </Typography>
        <ProvenanceBadge
          sourceType={String(provenance.source_type ?? '')}
          confidence={String(provenance.confidence ?? '')}
        />
      </Stack>
      <Typography color="text.secondary">
        Примите или отклоните строки. Числовые параметры надёжности из
        Fabricate/AI по умолчанию не импортируются.
      </Typography>
      {error ? <Alert severity="error">{error}</Alert> : null}
      <Box sx={{ height: 480, width: '100%' }}>
        <DataGrid
          rows={rows}
          columns={columns}
          loading={proposalQuery.isLoading}
          disableRowSelectionOnClick
          pageSizeOptions={[25, 50]}
          initialState={{
            pagination: { paginationModel: { pageSize: 25 } },
          }}
        />
      </Box>
      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button
          variant="contained"
          disabled={acceptedCount === 0 || commitMutation.isPending}
          onClick={() => commitMutation.mutate()}
        >
          Записать принятое в Domain DB ({acceptedCount})
        </Button>
        <Button
          onClick={() => {
            for (const item of rows) {
              if (item.decision === 'PENDING') {
                decideMutation.mutate({
                  itemId: item.id,
                  decision: 'ACCEPTED',
                })
              }
            }
          }}
        >
          Принять все ожидающие
        </Button>
        <Button component={RouterLink} to="/systems">
          Отмена
        </Button>
      </Box>
    </Stack>
  )
}

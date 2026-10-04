import { Alert, Box, Button, Stack, Typography } from '@mui/material'
import { DataGrid, type GridColDef } from '@mui/x-data-grid'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { aiApi } from '../../api/resources'
import type { ProposalItem } from '../../api/types'
import { ProvenanceBadge } from '../../components/ProvenanceBadge'
import { ProvenancePanel } from '../../components/ProvenancePanel'

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
    mutationFn: ({ itemId, decision }: { itemId: string; decision: string }) =>
      aiApi.decideItem(itemId, { decision }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['proposal', proposalId],
      })
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err.message : 'Ошибка решения')
    },
  })

  const commitMutation = useMutation({
    mutationFn: () => {
      const brief = proposalQuery.data?.payload?.brief as
        | { summary?: string; plant_type?: string }
        | undefined
      const fromBrief =
        brief?.summary?.split('.')[0]?.trim() ||
        brief?.plant_type?.replace(/_/g, ' ')
      return aiApi.commitProposal(proposalId, {
        system_name: fromBrief || proposalQuery.data?.title,
        create_system: true,
      })
    },
    onSuccess: (result) => {
      navigate(`/systems/${result.system_id}`)
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err.message : 'Ошибка commit')
    },
  })

  const [selectedItem, setSelectedItem] = useState<ProposalItem | null>(null)
  const rows = proposalQuery.data?.items ?? []
  const acceptedCount = rows.filter((item) =>
    ['ACCEPTED', 'EDITED'].includes(item.decision),
  ).length
  const firstSuggestion =
    selectedItem?.reference_suggestions?.find(
      (item) => item.kind === 'parameter',
    ) ?? null

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
      {
        field: 'reference_suggestions',
        headerName: 'OREDA/ISO',
        width: 120,
        valueGetter: (_value, row) =>
          row.reference_suggestions?.length
            ? String(row.reference_suggestions.length)
            : '—',
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
        Примите или отклоните строки. Сначала справочник OREDA/ISO, затем
        AI_ESTIMATE с низкой уверенностью. Числовые параметры из Fabricate/AI по
        умолчанию не импортируются.
      </Typography>
      {proposalQuery.data?.reference_priority ? (
        <Alert severity="info">
          {proposalQuery.data.reference_priority}{' '}
          <Button component={RouterLink} to="/reference" size="small">
            Открыть справочник
          </Button>
        </Alert>
      ) : null}
      {error ? <Alert severity="error">{error}</Alert> : null}
      <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
        <Box sx={{ height: 480, flex: 2, width: '100%' }}>
          <DataGrid
            rows={rows}
            columns={columns}
            loading={proposalQuery.isLoading}
            disableRowSelectionOnClick
            onRowClick={(params) => setSelectedItem(params.row as ProposalItem)}
            pageSizeOptions={[25, 50]}
            initialState={{
              pagination: { paginationModel: { pageSize: 25 } },
            }}
          />
        </Box>
        <Box sx={{ flex: 1, minWidth: 240 }}>
          <Typography variant="h6" gutterBottom>
            Provenance / OREDA
          </Typography>
          <ProvenancePanel
            value={firstSuggestion?.value}
            unit={firstSuggestion?.unit}
            sourceType={
              firstSuggestion?.source_type ??
              String(provenance.source_type ?? 'AI_ESTIMATE')
            }
            sourceDocument={firstSuggestion?.source_document}
            sourceReference={
              firstSuggestion?.source_reference ??
              String(provenance.source_reference ?? '')
            }
            confidence={
              firstSuggestion?.confidence ??
              String(provenance.confidence ?? 'LOW')
            }
            generatedBy={String(provenance.generated_by ?? '')}
            generatedAt={String(provenance.generated_at ?? '')}
          />
          {selectedItem?.reference_suggestions?.length ? (
            <Typography variant="caption" color="text.secondary">
              Подсказок справочника: {selectedItem.reference_suggestions.length}
            </Typography>
          ) : (
            <Typography variant="caption" color="text.secondary">
              Нет совпадений OREDA/ISO — оставьте UNKNOWN или оценку.
            </Typography>
          )}
        </Box>
      </Stack>
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

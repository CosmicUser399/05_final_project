import { Alert, Button, Stack, Typography } from '@mui/material'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { ApiError } from '../../api/client'
import { reliabilityApi } from '../../api/resources'
import type { ValidationReport } from '../../api/types'
import { shortHash } from '../results/format'
import { prepareAndCompileReliability } from './prepareMinimalModel'

interface Props {
  versionId: string
}

export function ReliabilityPanel({ versionId }: Props) {
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const [report, setReport] = useState<ValidationReport | null>(null)

  const modelQuery = useQuery({
    queryKey: ['reliability', versionId],
    queryFn: () => reliabilityApi.getLatest(versionId),
    enabled: Boolean(versionId),
    retry: false,
  })

  const invalidate = async () => {
    await queryClient.invalidateQueries({
      queryKey: ['reliability', versionId],
    })
  }

  const validateMutation = useMutation({
    mutationFn: () => reliabilityApi.validate(versionId),
    onSuccess: (result) => {
      setReport(result)
      setError(null)
    },
    onError: (err: unknown) => {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Не удалось выполнить валидацию',
      )
    },
  })

  const compileMutation = useMutation({
    mutationFn: () => reliabilityApi.generate(versionId, 'compiled from UI'),
    onSuccess: async () => {
      setError(null)
      setReport(null)
      await invalidate()
    },
    onError: (err: unknown) => {
      setError(
        err instanceof ApiError
          ? `${err.code}: ${err.message}`
          : 'Компиляция не удалась',
      )
      void validateMutation.mutate()
    },
  })

  const prepareMutation = useMutation({
    mutationFn: () => prepareAndCompileReliability(versionId),
    onSuccess: async () => {
      setError(null)
      setReport(null)
      await invalidate()
    },
    onError: (err: unknown) => {
      setError(
        err instanceof ApiError
          ? `${err.code}: ${err.message}`
          : 'Подготовка модели не удалась',
      )
      void validateMutation.mutate()
    },
  })

  const model = modelQuery.data
  const busy =
    compileMutation.isPending ||
    prepareMutation.isPending ||
    validateMutation.isPending

  return (
    <Stack spacing={1.5}>
      <Typography variant="h6">Reliability Model</Typography>
      <Typography variant="body2" color="text.secondary">
        Симуляция требует скомпилированный снимок (`POST
        /reliability/generate`). Без failure modes и production impact для
        критичного оборудования компиляция отклоняется.
      </Typography>
      {model ? (
        <Alert severity="success">
          Модель готова: {shortHash(model.model_hash)}; status=
          {model.validation_status}; id={model.id.slice(0, 8)}…
        </Alert>
      ) : (
        <Alert severity="warning">
          Reliability model ещё не скомпилирован для этой версии.
        </Alert>
      )}
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
        <Button
          variant="outlined"
          disabled={!versionId || busy}
          onClick={() => validateMutation.mutate()}
        >
          Проверить модель
        </Button>
        <Button
          variant="outlined"
          disabled={!versionId || busy}
          onClick={() => compileMutation.mutate()}
        >
          Скомпилировать
        </Button>
        <Button
          variant="contained"
          disabled={!versionId || busy}
          onClick={() => prepareMutation.mutate()}
        >
          Подготовить и скомпилировать
        </Button>
      </Stack>
      <Typography variant="caption" color="text.secondary">
        «Подготовить…» добавит минимальные failure mode / CM / production impact
        там, где их нет, затем скомпилирует снимок.
      </Typography>
      {error ? <Alert severity="error">{error}</Alert> : null}
      {report ? (
        <Alert severity={report.is_valid ? 'success' : 'warning'}>
          Валидация: {report.is_valid ? 'OK' : 'есть замечания'} (
          {report.issues.length})
          {!report.is_valid ? (
            <Stack component="ul" sx={{ pl: 2, mb: 0, mt: 1 }}>
              {report.issues.slice(0, 12).map((issue) => (
                <Typography
                  component="li"
                  variant="body2"
                  key={`${issue.code}-${issue.entity_id ?? issue.message}`}
                >
                  {issue.code}: {issue.message}
                </Typography>
              ))}
            </Stack>
          ) : null}
        </Alert>
      ) : null}
    </Stack>
  )
}

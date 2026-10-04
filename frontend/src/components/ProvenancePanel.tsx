import { Stack, Typography } from '@mui/material'

import { ProvenanceBadge } from './ProvenanceBadge'

interface Props {
  value?: string | number | null
  unit?: string | null
  sourceType?: string | null
  sourceDocument?: string | null
  sourceReference?: string | null
  confidence?: string | null
  generatedBy?: string | null
  generatedAt?: string | null
}

export function ProvenancePanel({
  value,
  unit,
  sourceType,
  sourceDocument,
  sourceReference,
  confidence,
  generatedBy,
  generatedAt,
}: Props) {
  const valueLabel =
    value === null || value === undefined
      ? '—'
      : unit
        ? `${value} ${unit}`
        : String(value)

  return (
    <Stack spacing={0.5}>
      <Typography variant="body2">Значение: {valueLabel}</Typography>
      <Stack direction="row" spacing={1} alignItems="center">
        <Typography variant="body2">Источник:</Typography>
        <ProvenanceBadge sourceType={sourceType} confidence={confidence} />
      </Stack>
      {sourceDocument ? (
        <Typography variant="body2" color="text.secondary">
          Документ: {sourceDocument}
        </Typography>
      ) : null}
      {sourceReference ? (
        <Typography variant="body2" color="text.secondary">
          Ссылка: {sourceReference}
        </Typography>
      ) : null}
      {generatedBy ? (
        <Typography variant="caption" color="text.secondary">
          Кто: {generatedBy}
          {generatedAt ? ` · ${generatedAt}` : ''}
        </Typography>
      ) : null}
    </Stack>
  )
}

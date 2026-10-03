import { Chip } from '@mui/material'

const COLORS: Record<string, 'default' | 'warning' | 'success' | 'info'> = {
  AI_ESTIMATE: 'warning',
  OREDA: 'success',
  MANUFACTURER_DATA: 'info',
  USER_DEFINED: 'default',
  ENGINEERING_ASSUMPTION: 'warning',
}

interface Props {
  sourceType?: string | null
  confidence?: string | null
}

export function ProvenanceBadge({ sourceType, confidence }: Props) {
  if (!sourceType) {
    return null
  }
  const label = confidence ? `${sourceType} · ${confidence}` : sourceType
  return (
    <Chip
      size="small"
      color={COLORS[sourceType] ?? 'default'}
      label={label}
      variant={sourceType === 'AI_ESTIMATE' ? 'filled' : 'outlined'}
    />
  )
}

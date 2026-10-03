import { Chip, CircularProgress } from '@mui/material'

import { useHealth } from './useHealth'

export function BackendStatus() {
  const { data, isPending, isError } = useHealth()

  if (isPending) {
    return <CircularProgress size={20} aria-label="Проверка бэкенда" />
  }
  if (isError || data.status !== 'ok') {
    return <Chip color="error" size="small" label="Бэкенд недоступен" />
  }
  return (
    <Chip color="success" size="small" label={`Бэкенд OK · v${data.version}`} />
  )
}

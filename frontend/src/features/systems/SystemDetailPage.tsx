import {
  Alert,
  CircularProgress,
  Stack,
  Tab,
  Tabs,
  Typography,
} from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'

import { systemsApi } from '../../api/resources'
import { EquipmentGraph } from '../equipment/EquipmentGraph'
import { EquipmentTable } from '../equipment/EquipmentTable'
import { ReliabilityPanel } from '../reliability/ReliabilityPanel'

export function SystemDetailPage() {
  const { systemId = '' } = useParams()
  const [tab, setTab] = useState(0)

  const systemQuery = useQuery({
    queryKey: ['system', systemId],
    queryFn: () => systemsApi.get(systemId),
    enabled: Boolean(systemId),
  })
  const versionsQuery = useQuery({
    queryKey: ['versions', systemId],
    queryFn: () => systemsApi.versions(systemId),
    enabled: Boolean(systemId),
  })

  const versionId = useMemo(() => {
    const versions = versionsQuery.data ?? []
    if (versions.length === 0) {
      return null
    }
    const latest = [...versions].sort(
      (a, b) => b.version_number - a.version_number,
    )[0]
    return latest?.id ?? null
  }, [versionsQuery.data])

  if (systemQuery.isLoading || versionsQuery.isLoading) {
    return <CircularProgress />
  }
  if (systemQuery.isError || !systemQuery.data) {
    return <Alert severity="error">Система не найдена</Alert>
  }

  return (
    <Stack spacing={2}>
      <Typography variant="h4">{systemQuery.data.name}</Typography>
      <Typography color="text.secondary">
        {systemQuery.data.description || 'Без описания'}
      </Typography>
      {versionId ? (
        <Typography variant="body2">
          Активная версия: {versionId}
        </Typography>
      ) : (
        <Alert severity="warning">У системы нет версий</Alert>
      )}
      <Tabs value={tab} onChange={(_, value: number) => setTab(value)}>
        <Tab label="Оборудование" />
        <Tab label="Граф" />
        <Tab label="Надёжность" />
      </Tabs>
      {versionId && tab === 0 ? (
        <EquipmentTable versionId={versionId} />
      ) : null}
      {versionId && tab === 1 ? (
        <EquipmentGraph versionId={versionId} />
      ) : null}
      {versionId && tab === 2 ? (
        <ReliabilityPanel versionId={versionId} />
      ) : null}
    </Stack>
  )
}

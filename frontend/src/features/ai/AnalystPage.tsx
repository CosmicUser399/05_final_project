import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  FormControl,
  InputLabel,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link as RouterLink, useSearchParams } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { aiApi, simulationsApi, systemsApi } from '../../api/resources'
import type {
  AnalystChatResponse,
  AnalystReference,
  SimulationStatus,
  System,
  SystemVersion,
} from '../../api/types'

interface ChatTurn {
  role: 'user' | 'assistant'
  text: string
  response?: AnalystChatResponse
}

export function AnalystPage() {
  const [searchParams] = useSearchParams()
  const [systemId, setSystemId] = useState(
    searchParams.get('systemId') ?? '',
  )
  const [versionId, setVersionId] = useState(
    searchParams.get('versionId') ?? '',
  )
  const [runId, setRunId] = useState(
    searchParams.get('runId') ?? '',
  )
  const [message, setMessage] = useState(
    'Какие метрики доступности и потерь производства показывает симуляция?',
  )
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [error, setError] = useState<string | null>(null)

  const systemsQuery = useQuery({
    queryKey: ['systems'],
    queryFn: () => systemsApi.list(),
  })

  const versionsQuery = useQuery({
    queryKey: ['versions', systemId],
    queryFn: () => systemsApi.versions(systemId),
    enabled: Boolean(systemId),
  })

  const runsQuery = useQuery({
    queryKey: ['simulations', versionId],
    queryFn: () => simulationsApi.list(versionId),
    enabled: Boolean(versionId),
  })

  const completedRuns = useMemo(
    () =>
      (runsQuery.data ?? []).filter(
        (row: SimulationStatus) => row.status === 'COMPLETED',
      ),
    [runsQuery.data],
  )

  const chatMutation = useMutation({
    mutationFn: () =>
      aiApi.chat({
        message,
        context: {
          system_id: systemId || null,
          version_id: versionId || null,
          simulation_run_id: runId || null,
        },
      }),
    onMutate: () => {
      setError(null)
      setTurns((prev) => [...prev, { role: 'user', text: message }])
    },
    onSuccess: (response) => {
      setTurns((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: response.answer,
          response,
        },
      ])
    },
    onError: (err: unknown) => {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Ошибка AI Analyst',
      )
    },
  })

  return (
    <Stack spacing={2} maxWidth={960}>
      <Typography variant="h4">AI Analyst</Typography>
      <Typography color="text.secondary">
        Ответы строятся только через typed tools по сохранённым
        результатам симуляции и модели. Числа вне tool-результатов
        отклоняются.
      </Typography>

      <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
        <FormControl fullWidth size="small">
          <InputLabel id="analyst-system">Система</InputLabel>
          <Select
            labelId="analyst-system"
            label="Система"
            value={systemId}
            onChange={(event) => {
              setSystemId(event.target.value)
              setVersionId('')
              setRunId('')
            }}
          >
            <MenuItem value="">
              <em>Не выбрано</em>
            </MenuItem>
            {(systemsQuery.data ?? []).map((row: System) => (
              <MenuItem key={row.id} value={row.id}>
                {row.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <FormControl fullWidth size="small" disabled={!systemId}>
          <InputLabel id="analyst-version">Версия</InputLabel>
          <Select
            labelId="analyst-version"
            label="Версия"
            value={versionId}
            onChange={(event) => {
              setVersionId(event.target.value)
              setRunId('')
            }}
          >
            <MenuItem value="">
              <em>Не выбрано</em>
            </MenuItem>
            {(versionsQuery.data ?? []).map((row: SystemVersion) => (
              <MenuItem key={row.id} value={row.id}>
                v{row.version_number} ({row.status})
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <FormControl fullWidth size="small" disabled={!versionId}>
          <InputLabel id="analyst-run">Симуляция</InputLabel>
          <Select
            labelId="analyst-run"
            label="Симуляция"
            value={runId}
            onChange={(event) => setRunId(event.target.value)}
          >
            <MenuItem value="">
              <em>Не выбрано</em>
            </MenuItem>
            {completedRuns.map((row) => (
              <MenuItem key={row.id} value={row.id}>
                {row.id.slice(0, 8)}… seed={row.random_seed}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Stack>

      <TextField
        label="Вопрос"
        value={message}
        onChange={(event) => setMessage(event.target.value)}
        multiline
        minRows={3}
        fullWidth
      />

      <Stack direction="row" spacing={1}>
        <Button
          variant="contained"
          disabled={!message.trim() || chatMutation.isPending}
          onClick={() => chatMutation.mutate()}
        >
          Спросить
        </Button>
        {runId ? (
          <Button
            component={RouterLink}
            to={`/simulations/${runId}`}
            variant="outlined"
          >
            К результатам
          </Button>
        ) : null}
        {chatMutation.isPending ? <CircularProgress size={24} /> : null}
      </Stack>

      {error ? <Alert severity="error">{error}</Alert> : null}

      <Divider />

      <Stack spacing={2}>
        {turns.map((turn, index) => (
          <Box
            key={`${turn.role}-${index}`}
            sx={{
              p: 1.5,
              bgcolor:
                turn.role === 'user'
                  ? 'action.hover'
                  : 'background.paper',
              borderLeft: 3,
              borderColor:
                turn.role === 'user' ? 'primary.main' : 'success.main',
            }}
          >
            <Typography variant="subtitle2" gutterBottom>
              {turn.role === 'user' ? 'Вы' : 'Analyst'}
            </Typography>
            <Typography
              component="pre"
              sx={{
                whiteSpace: 'pre-wrap',
                fontFamily: 'inherit',
                m: 0,
              }}
            >
              {turn.text}
            </Typography>
            {turn.response ? (
              <AnswerMeta response={turn.response} />
            ) : null}
          </Box>
        ))}
      </Stack>
    </Stack>
  )
}

function AnswerMeta({ response }: { response: AnalystChatResponse }) {
  return (
    <Stack spacing={1} mt={1.5}>
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
        <Chip
          size="small"
          color={response.grounded ? 'success' : 'warning'}
          label={
            response.grounded
              ? 'Grounded'
              : 'Not grounded'
          }
        />
        {response.model ? (
          <Chip size="small" label={`model: ${response.model}`} />
        ) : null}
        <Chip
          size="small"
          variant="outlined"
          label={`tools: ${response.tool_calls.length}`}
        />
      </Stack>
      {response.references.length > 0 ? (
        <List dense disablePadding>
          {response.references.map((ref: AnalystReference) => (
            <ListItem key={`${ref.kind}-${ref.entity_id}-${ref.label}`} disableGutters>
              <ListItemText
                primary={`${ref.kind}: ${ref.label}`}
                secondary={ref.entity_id}
              />
            </ListItem>
          ))}
        </List>
      ) : null}
      {response.tool_calls.length > 0 ? (
        <Typography variant="body2" color="text.secondary">
          Вызовы:{' '}
          {response.tool_calls
            .map((call) => `${call.name}${call.ok ? '' : '!'}`)
            .join(', ')}
        </Typography>
      ) : null}
    </Stack>
  )
}

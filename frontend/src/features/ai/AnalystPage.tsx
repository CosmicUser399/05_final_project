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
import { useEffect, useMemo, useState } from 'react'
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

const STORAGE_PREFIX = 'ai-analyst-chat:v1'

function storageKey(
  systemId: string,
  versionId: string,
  runId: string,
): string {
  return `${STORAGE_PREFIX}:${systemId}:${versionId}:${runId}`
}

function loadTurns(
  systemId: string,
  versionId: string,
  runId: string,
): ChatTurn[] {
  if (!systemId && !versionId && !runId) {
    return []
  }
  try {
    const raw = localStorage.getItem(storageKey(systemId, versionId, runId))
    if (!raw) {
      return []
    }
    const parsed = JSON.parse(raw) as ChatTurn[]
    if (!Array.isArray(parsed)) {
      return []
    }
    return parsed.filter(
      (row) =>
        (row.role === 'user' || row.role === 'assistant') &&
        typeof row.text === 'string',
    )
  } catch {
    return []
  }
}

function saveTurns(
  systemId: string,
  versionId: string,
  runId: string,
  turns: ChatTurn[],
): void {
  if (!systemId && !versionId && !runId) {
    return
  }
  try {
    const slim = turns.map((turn) => ({
      role: turn.role,
      text: turn.text,
      response: turn.response
        ? {
            answer: turn.response.answer,
            grounded: turn.response.grounded,
            model: turn.response.model,
            references: turn.response.references,
            tool_calls: turn.response.tool_calls.map((call) => ({
              name: call.name,
              ok: call.ok,
              arguments: {},
              result: {},
              error: call.error,
            })),
          }
        : undefined,
    }))
    localStorage.setItem(
      storageKey(systemId, versionId, runId),
      JSON.stringify(slim),
    )
  } catch {
    // Ignore quota / private mode errors.
  }
}

export function AnalystPage() {
  const [searchParams] = useSearchParams()
  const [systemId, setSystemId] = useState(searchParams.get('systemId') ?? '')
  const [versionId, setVersionId] = useState(
    searchParams.get('versionId') ?? '',
  )
  const [runId, setRunId] = useState(searchParams.get('runId') ?? '')
  const [message, setMessage] = useState(
    'Какие метрики доступности и потерь производства показывает симуляция?',
  )
  const [turns, setTurns] = useState<ChatTurn[]>(() =>
    loadTurns(
      searchParams.get('systemId') ?? '',
      searchParams.get('versionId') ?? '',
      searchParams.get('runId') ?? '',
    ),
  )
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setTurns(loadTurns(systemId, versionId, runId))
  }, [systemId, versionId, runId])

  useEffect(() => {
    saveTurns(systemId, versionId, runId, turns)
  }, [systemId, versionId, runId, turns])

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
    mutationFn: (payload: { text: string; history: ChatTurn[] }) =>
      aiApi.chat({
        message: payload.text,
        context: {
          system_id: systemId || null,
          version_id: versionId || null,
          simulation_run_id: runId || null,
        },
        history: payload.history.slice(-20).map((turn) => ({
          role: turn.role,
          content: turn.text,
        })),
      }),
    onMutate: (payload) => {
      setError(null)
      setTurns((prev) => [...prev, { role: 'user', text: payload.text }])
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
      setMessage('')
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err.message : 'Ошибка AI Analyst')
    },
  })

  const ask = () => {
    const text = message.trim()
    if (!text || chatMutation.isPending) {
      return
    }
    chatMutation.mutate({ text, history: turns })
  }

  const clearDialog = () => {
    setTurns([])
    try {
      localStorage.removeItem(storageKey(systemId, versionId, runId))
    } catch {
      // ignore
    }
  }

  return (
    <Stack spacing={2} maxWidth={960}>
      <Typography variant="h4">AI Analyst</Typography>
      <Typography color="text.secondary">
        Диалоговый аналитик по результатам симуляции и модели. Числа берутся
        только из typed tools; история чата сохраняется в браузере.
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

      <Divider />

      <Stack spacing={2} minHeight={240}>
        {turns.length === 0 ? (
          <Typography color="text.secondary">
            Задайте вопрос — диалог сохранится для выбранного контекста.
          </Typography>
        ) : null}
        {turns.map((turn, index) => (
          <Box
            key={`${turn.role}-${index}`}
            sx={{
              p: 1.5,
              bgcolor:
                turn.role === 'user' ? 'action.hover' : 'background.paper',
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
            {turn.response ? <AnswerMeta response={turn.response} /> : null}
          </Box>
        ))}
      </Stack>

      {error ? <Alert severity="error">{error}</Alert> : null}

      <TextField
        label="Вопрос"
        value={message}
        onChange={(event) => setMessage(event.target.value)}
        multiline
        minRows={3}
        fullWidth
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault()
            ask()
          }
        }}
      />

      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
        <Button
          variant="contained"
          disabled={!message.trim() || chatMutation.isPending}
          onClick={ask}
        >
          Спросить
        </Button>
        <Button
          variant="outlined"
          color="inherit"
          disabled={turns.length === 0 || chatMutation.isPending}
          onClick={clearDialog}
        >
          Очистить диалог
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
          label={response.grounded ? 'Grounded' : 'Not grounded'}
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
            <ListItem
              key={`${ref.kind}-${ref.entity_id}-${ref.label}`}
              disableGutters
            >
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

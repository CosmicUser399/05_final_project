import {
  Alert,
  Box,
  Button,
  FormControl,
  InputLabel,
  LinearProgress,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { useMutation } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { aiApi } from '../../api/resources'
import type { GenerationJob } from '../../api/types'

export function GenerateSystemPage() {
  const navigate = useNavigate()
  const [description, setDescription] = useState(
    'Установка производства полистирола мощностью 100 тысяч тонн в год',
  )
  const [provider, setProvider] = useState<'openai' | 'fabricate'>('openai')
  const [job, setJob] = useState<GenerationJob | null>(null)
  const [error, setError] = useState<string | null>(null)

  const startMutation = useMutation({
    mutationFn: () =>
      aiApi.generateSystem({
        description,
        provider,
        process_inline: true,
      }),
    onSuccess: (created) => {
      setJob(created)
      setError(null)
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err.message : 'Ошибка генерации')
    },
  })

  useEffect(() => {
    if (!job || job.status === 'READY_FOR_REVIEW') {
      return
    }
    if (job.status === 'FAILED' || job.status === 'CANCELLED') {
      return
    }
    const timer = window.setInterval(async () => {
      try {
        const next = await aiApi.getJob(job.id)
        setJob(next)
      } catch (err) {
        setError(err instanceof ApiError ? err.message : 'Ошибка статуса')
      }
    }, 1000)
    return () => window.clearInterval(timer)
  }, [job])

  useEffect(() => {
    if (job?.status === 'READY_FOR_REVIEW' && job.proposal_id) {
      navigate(`/ai/proposals/${job.proposal_id}`)
    }
  }, [job, navigate])

  return (
    <Stack spacing={2} maxWidth={720}>
      <Typography variant="h4">Генерация базы оборудования</Typography>
      <Typography color="text.secondary">
        Описание проходит через OpenAI или Fabricate, затем staging и
        обязательное ревью. В Domain DB ничего не пишется до принятия.
      </Typography>
      <TextField
        label="Описание установки"
        multiline
        minRows={4}
        value={description}
        onChange={(event) => setDescription(event.target.value)}
      />
      <FormControl sx={{ maxWidth: 280 }}>
        <InputLabel id="provider-label">Провайдер</InputLabel>
        <Select
          labelId="provider-label"
          label="Провайдер"
          value={provider}
          onChange={(event) =>
            setProvider(event.target.value as 'openai' | 'fabricate')
          }
        >
          <MenuItem value="openai">OpenAI (быстрый)</MenuItem>
          <MenuItem value="fabricate">Fabricate (массовая структура)</MenuItem>
        </Select>
      </FormControl>
      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button
          variant="contained"
          disabled={!description.trim() || startMutation.isPending}
          onClick={() => startMutation.mutate()}
        >
          Запустить
        </Button>
        <Button component={RouterLink} to="/systems">
          К системам
        </Button>
      </Box>
      {error ? <Alert severity="error">{error}</Alert> : null}
      {job ? (
        <Stack spacing={1}>
          <Typography variant="body2">
            Задача {job.id} · {job.status}
            {job.progress_message ? ` · ${job.progress_message}` : ''}
          </Typography>
          <LinearProgress variant="determinate" value={job.progress_pct ?? 0} />
          {job.error_message ? (
            <Alert severity="error">{job.error_message}</Alert>
          ) : null}
        </Stack>
      ) : null}
    </Stack>
  )
}

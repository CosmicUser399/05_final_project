import { Alert, Button, Stack, Typography } from '@mui/material'
import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'

import { demoApi } from '../api/resources'
import { PlaceholderPage } from '../components/PlaceholderPage'

export function HomePage() {
  const navigate = useNavigate()
  const [seedError, setSeedError] = useState<string | null>(null)
  const seedMutation = useMutation({
    mutationFn: () => demoApi.seedUpp100({ write_seed_file: false }),
    onSuccess: (result) => {
      setSeedError(null)
      void navigate(`/systems/${result.system_id}`)
    },
    onError: (err: Error) => setSeedError(err.message),
  })

  return (
    <Stack spacing={2}>
      <Typography variant="h4">AI Reliability Modelling</Typography>
      <Typography color="text.secondary">
        Платформа моделирования надёжности, доступности и ремонтопригодности
        (RAM). Доступны CRUD систем/оборудования, AI/Fabricate генерация со
        staging-ревью, граф оборудования, сценарии и дашборд результатов Monte
        Carlo.
      </Typography>
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
        <Button component={RouterLink} to="/systems" variant="contained">
          Системы
        </Button>
        <Button
          variant="outlined"
          onClick={() => seedMutation.mutate()}
          disabled={seedMutation.isPending}
        >
          Загрузить демо УПП-100
        </Button>
        <Button component={RouterLink} to="/ai/generate" variant="outlined">
          AI-генерация
        </Button>
        <Button component={RouterLink} to="/ai/analyst" variant="outlined">
          AI Analyst
        </Button>
        <Button component={RouterLink} to="/simulations" variant="outlined">
          Симуляции
        </Button>
        <Button component={RouterLink} to="/scenarios" variant="outlined">
          Сценарии
        </Button>
        <Button component={RouterLink} to="/reference" variant="outlined">
          Справочник
        </Button>
      </Stack>
      {seedError ? <Alert severity="error">{seedError}</Alert> : null}
      <Typography variant="caption" color="text.secondary">
        Демо-датасет УПП-100 предназначен только для тестирования ПО (включая
        PF-демо P-101).
      </Typography>
    </Stack>
  )
}

export function NotFoundPage() {
  return (
    <PlaceholderPage
      title="Страница не найдена"
      description="Проверьте адрес или воспользуйтесь навигацией."
    />
  )
}

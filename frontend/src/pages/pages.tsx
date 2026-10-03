import { Button, Stack, Typography } from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'

import { PlaceholderPage } from '../components/PlaceholderPage'

export function HomePage() {
  return (
    <Stack spacing={2}>
      <Typography variant="h4">AI Reliability Modelling</Typography>
      <Typography color="text.secondary">
        Платформа моделирования надёжности, доступности и
        ремонтопригодности (RAM). Доступны CRUD систем/оборудования,
        AI/Fabricate генерация со staging-ревью, граф оборудования и
        сценарии сравнения стратегий ТО.
      </Typography>
      <Stack direction="row" spacing={1}>
        <Button component={RouterLink} to="/systems" variant="contained">
          Системы
        </Button>
        <Button component={RouterLink} to="/ai/generate" variant="outlined">
          AI-генерация
        </Button>
        <Button component={RouterLink} to="/scenarios" variant="outlined">
          Сценарии
        </Button>
      </Stack>
    </Stack>
  )
}

export function SimulationsPage() {
  return (
    <PlaceholderPage
      title="Симуляции"
      description="Запуски Monte Carlo и результаты появятся в фазе P9."
    />
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

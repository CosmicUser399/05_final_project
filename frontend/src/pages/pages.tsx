import { PlaceholderPage } from '../components/PlaceholderPage'

export function HomePage() {
  return (
    <PlaceholderPage
      title="AI Reliability Modelling"
      description="Платформа моделирования надёжности, доступности и ремонтопригодности (RAM). Каркас приложения готов."
    />
  )
}

export function SystemsPage() {
  return (
    <PlaceholderPage
      title="Системы"
      description="Список систем и версий моделей появится в фазе P7."
    />
  )
}

export function SimulationsPage() {
  return (
    <PlaceholderPage
      title="Симуляции"
      description="Запуски Monte Carlo и результаты появятся в фазах P5 и P9."
    />
  )
}

export function ScenariosPage() {
  return (
    <PlaceholderPage
      title="Сценарии"
      description="Сценарии и сравнение появятся в фазе P8."
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

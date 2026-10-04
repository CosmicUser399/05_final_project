export interface NavItem {
  path: string
  label: string
}

export const NAV_ITEMS: readonly NavItem[] = [
  { path: '/', label: 'Главная' },
  { path: '/systems', label: 'Системы' },
  { path: '/ai/generate', label: 'AI-генерация' },
  { path: '/ai/analyst', label: 'AI Analyst' },
  { path: '/simulations', label: 'Симуляции' },
  { path: '/scenarios', label: 'Сценарии' },
]

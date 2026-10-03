export interface NavItem {
  path: string
  label: string
}

/** Sections are filled in by later phases (P7+). */
export const NAV_ITEMS: readonly NavItem[] = [
  { path: '/', label: 'Главная' },
  { path: '/systems', label: 'Системы' },
  { path: '/simulations', label: 'Симуляции' },
  { path: '/scenarios', label: 'Сценарии' },
]

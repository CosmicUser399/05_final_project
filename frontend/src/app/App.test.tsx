import { render, screen } from '@testing-library/react'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { Providers } from './Providers'
import { createQueryClient } from './queryClient'
import { routes } from './routes'

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  return render(
    <Providers client={createQueryClient()}>
      <RouterProvider router={router} />
    </Providers>,
  )
}

describe('app shell', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        statusText: 'OK',
        json: () => Promise.resolve({ status: 'ok', version: '0.1.0' }),
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders navigation and the home page', async () => {
    renderAt('/')

    expect(
      screen.getAllByRole('link', { name: 'Системы' }).length,
    ).toBeGreaterThan(0)
    expect(
      screen.getByRole('heading', {
        name: 'AI Reliability Modelling',
        level: 4,
      }),
    ).toBeInTheDocument()
    expect(await screen.findByText(/Бэкенд OK/)).toBeInTheDocument()
  })

  it('renders a section page by route', () => {
    renderAt('/scenarios')

    expect(
      screen.getByRole('heading', { name: 'Сценарии', level: 4 }),
    ).toBeInTheDocument()
  })

  it('renders simulations results list page', () => {
    renderAt('/simulations')

    expect(
      screen.getByRole('heading', { name: 'Симуляции', level: 4 }),
    ).toBeInTheDocument()
  })

  it('renders AI generation page', () => {
    renderAt('/ai/generate')

    expect(
      screen.getByRole('heading', {
        name: 'Генерация базы оборудования',
        level: 4,
      }),
    ).toBeInTheDocument()
  })

  it('renders the not-found page for unknown routes', () => {
    renderAt('/unknown/path')

    expect(screen.getByText('Страница не найдена')).toBeInTheDocument()
  })

  it('shows an error chip when the backend is down', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))

    renderAt('/')

    expect(await screen.findByText('Бэкенд недоступен')).toBeInTheDocument()
  })
})

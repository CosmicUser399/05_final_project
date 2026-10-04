import { expect, test } from '@playwright/test'

/**
 * UI smoke for Package §101 entry points.
 * Full 30-step flow is covered by backend
 * ``tests/api/test_p12_acceptance.py``.
 */
test.describe('MVP UI smoke', () => {
  test('home page exposes demo and navigation', async ({ page }) => {
    await page.goto('/')
    await expect(
      page.getByRole('heading', { name: 'AI Reliability Modelling' }),
    ).toBeVisible()
    await expect(
      page.getByRole('button', { name: 'Загрузить демо УПП-100' }),
    ).toBeVisible()
    await expect(page.getByRole('link', { name: 'Системы' })).toBeVisible()
  })

  test('health is reachable through the reverse proxy', async ({
    request,
  }) => {
    const response = await request.get('/health')
    expect(response.ok()).toBeTruthy()
    const body = await response.json()
    expect(body.status).toBe('ok')
  })
})

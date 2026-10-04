import { describe, expect, it } from 'vitest'

import { formatNum, formatPct, shortHash } from './format'

describe('results format helpers', () => {
  it('formats finite numbers and nulls', () => {
    expect(formatNum(null)).toBe('—')
    expect(formatNum(0.123456)).toMatch(/0\.123/)
    expect(formatNum(1e7)).toMatch(/e\+/)
  })

  it('formats proportions as percent', () => {
    expect(formatPct(0.95)).toBe('95.00 %')
    expect(formatPct(null)).toBe('—')
  })

  it('shortens hashes', () => {
    expect(shortHash('abcdefghijklmnop')).toBe('abcdefghijkl…')
    expect(shortHash('abc')).toBe('abc')
  })
})

import { describe, it, expect, beforeEach, afterEach } from 'vitest'

import {
  API_KEY_STORAGE_KEY,
  clearApiKeyValue,
  getApiKeyHeaderName,
  getApiKeyValue,
  setApiKeyValue,
} from './auth'

describe('auth helpers (strict)', () => {
  beforeEach(() => {
    window.localStorage.clear()
    ;(globalThis as any).__FORM_ANALYSIS_ENV__ = { VITE_API_KEY: '', VITE_API_KEY_HEADER: '' }
  })

  afterEach(() => {
    delete (globalThis as any).__FORM_ANALYSIS_ENV__
  })

  it('defaults header name to X-API-Key', () => {
    expect(getApiKeyHeaderName()).toBe('X-API-Key')
  })

  it('reads api key from localStorage first', () => {
    window.localStorage.setItem(API_KEY_STORAGE_KEY, '  abc  ')
    ;(globalThis as any).__FORM_ANALYSIS_ENV__.VITE_API_KEY = 'env'
    expect(getApiKeyValue()).toBe('abc')
  })

  it('falls back to env var when localStorage missing', () => {
    ;(globalThis as any).__FORM_ANALYSIS_ENV__.VITE_API_KEY = '  env123  '
    expect(getApiKeyValue()).toBe('env123')
  })

  it('uses custom header name from env when provided', () => {
    ;(globalThis as any).__FORM_ANALYSIS_ENV__.VITE_API_KEY_HEADER = '  Authorization  '
    expect(getApiKeyHeaderName()).toBe('Authorization')
  })

  it('setApiKeyValue stores trimmed key in localStorage (and getApiKeyValue reads it)', () => {
    setApiKeyValue('  abc123  ')
    expect(window.localStorage.getItem(API_KEY_STORAGE_KEY)).toBe('abc123')
    expect(getApiKeyValue()).toBe('abc123')
  })

  it('setApiKeyValue with empty input removes localStorage key', () => {
    window.localStorage.setItem(API_KEY_STORAGE_KEY, 'will-be-removed')
    setApiKeyValue('   ')
    expect(window.localStorage.getItem(API_KEY_STORAGE_KEY)).toBeNull()
  })

  it('clearApiKeyValue removes localStorage key', () => {
    window.localStorage.setItem(API_KEY_STORAGE_KEY, 'will-be-removed')
    clearApiKeyValue()
    expect(window.localStorage.getItem(API_KEY_STORAGE_KEY)).toBeNull()
  })
})

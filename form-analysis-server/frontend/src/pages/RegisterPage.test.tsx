import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { RegisterPage } from './RegisterPage'
import { API_KEY_STORAGE_KEY } from '../services/auth'

vi.mock('../components/common/ToastContext', () => ({
  useToast: () => ({
    showToast: vi.fn(),
  }),
}))

describe('RegisterPage (strict)', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('saves API key to localStorage and clears it', async () => {
    const user = userEvent.setup()

    render(<RegisterPage />)

    await act(async () => {
      await user.click(screen.getByRole('button', { name: '展開進階設定' }))
    })

    const input = screen.getByPlaceholderText('例如：abc123...')
    await act(async () => {
      await user.type(input, '  key-123  ')
    })

    await act(async () => {
      await user.click(screen.getByRole('button', { name: '保存 API key' }))
    })
    expect(window.localStorage.getItem(API_KEY_STORAGE_KEY)).toBe('key-123')

    await act(async () => {
      await user.click(screen.getByRole('button', { name: '清除 API key' }))
    })
    expect(window.localStorage.getItem(API_KEY_STORAGE_KEY)).toBeNull()
  })
})

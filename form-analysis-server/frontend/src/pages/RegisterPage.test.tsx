import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { RegisterPage } from './RegisterPage'
import { ADMIN_API_KEY_STORAGE_KEY } from '../services/adminAuth'

vi.mock('../components/common/ToastContext', () => ({
  useToast: () => ({
    showToast: vi.fn(),
  }),
}))

describe('RegisterPage (strict)', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('hides API key UI and gates admin init behind admin key', async () => {
    const user = userEvent.setup()

    render(<RegisterPage />)

    // First screen should not show API key / header content
    expect(screen.queryByText(/API key/i)).toBeNull()
    expect(screen.queryByText(/^Header$/i)).toBeNull()

    // Admin-only init content should not be visible until admin key is provided
    expect(screen.queryByRole('button', { name: '建立場域（Tenant）' })).toBeNull()

    await act(async () => {
      await user.click(screen.getByText('管理者（初始化用）'))
    })

    const input = screen.getByPlaceholderText('請貼上金鑰')
    await act(async () => {
      await user.type(input, '  admin-key-123  ')
    })

    await act(async () => {
      await user.click(screen.getByRole('button', { name: '啟用管理者模式' }))
    })
    expect(window.localStorage.getItem(ADMIN_API_KEY_STORAGE_KEY)).toBe('admin-key-123')

    // After enabling admin mode, init actions should appear
    expect(screen.getByRole('button', { name: '建立場域（Tenant）' })).toBeInTheDocument()
  })
})

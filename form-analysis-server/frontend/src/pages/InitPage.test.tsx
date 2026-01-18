import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { InitPage } from './InitPage'
import { ADMIN_API_KEY_STORAGE_KEY } from '../services/adminAuth'

vi.mock('../components/common/ToastContext', () => ({
  useToast: () => ({
    showToast: vi.fn(),
  }),
}))

describe.skip('InitPage (deprecated)', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('gates tenant bootstrap behind admin key', async () => {
    const user = userEvent.setup()

    render(<InitPage />)

    // Init actions should not be visible until admin key is provided.
    expect(screen.queryByRole('button', { name: '建立場域（Tenant）' })).toBeNull()

    const input = screen.getByPlaceholderText('請貼上金鑰')
    await act(async () => {
      await user.type(input, '  admin-key-123  ')
    })

    await act(async () => {
      await user.click(screen.getByRole('button', { name: '啟用管理者模式' }))
    })

    expect(window.localStorage.getItem(ADMIN_API_KEY_STORAGE_KEY)).toBe('admin-key-123')
    expect(screen.getByRole('button', { name: '建立場域（Tenant）' })).toBeInTheDocument()
  })
})

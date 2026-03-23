import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

import { RegisterPage } from './RegisterPage'

vi.mock('../components/common/ToastContext', () => ({
  useToast: () => ({
    showToast: vi.fn(),
  }),
}))

describe('RegisterPage (strict)', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('does not expose admin initialization controls', async () => {
    render(<RegisterPage />)

    // First screen should not show API key / header content
    expect(screen.queryByText(/API key/i)).toBeNull()
    expect(screen.queryByText(/^Header$/i)).toBeNull()

    // Init actions live on InitPage now.
    expect(screen.queryByText('管理者（初始化用）')).toBeNull()
    expect(screen.queryByRole('button', { name: '建立場域（Tenant）' })).toBeNull()
  })
})

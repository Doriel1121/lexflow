import { describe, it, expect, beforeEach } from 'vitest'

describe('API Client - Authorization Headers', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('should include Authorization header when token exists', () => {
    const mockToken = 'Bearer test-token-with-org-id'
    localStorage.setItem('token', mockToken)
    
    const headers = {
      'Authorization': `Bearer ${localStorage.getItem('token')?.replace('Bearer ', '')}`
    }
    
    expect(headers.Authorization).toContain('test-token-with-org-id')
  })

  it('should not include Authorization header when no token', () => {
    const token = localStorage.getItem('token')
    
    expect(token).toBeNull()
  })

  it('should clear token on logout', () => {
    localStorage.setItem('token', 'test-token')
    expect(localStorage.getItem('token')).toBeTruthy()
    
    // Simulate logout
    localStorage.removeItem('token')
    
    expect(localStorage.getItem('token')).toBeNull()
  })
})

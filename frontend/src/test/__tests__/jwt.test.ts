import { describe, it, expect } from 'vitest'

describe('JWT Token - Multi-Tenant', () => {
  it('should decode JWT token with org_id', () => {
    // Mock JWT token with org_id
    const token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6InRlc3RAZXhhbXBsZS5jb20iLCJ1c2VyX2lkIjoxLCJvcmdfaWQiOjEyMywicm9sZSI6IkxBV1lFUiJ9.xxx'
    
    // Decode JWT (base64)
    const payload = JSON.parse(atob(token.split('.')[1]))
    
    expect(payload.email).toBe('test@example.com')
    expect(payload.user_id).toBe(1)
    expect(payload.org_id).toBe(123)
    expect(payload.role).toBe('LAWYER')
  })

  it('should handle independent user with null org_id', () => {
    const token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6InNvbG9AbGF3eWVyLmNvbSIsInVzZXJfaWQiOjEsIm9yZ19pZCI6bnVsbCwicm9sZSI6IkxBV1lFUiJ9.xxx'
    
    const payload = JSON.parse(atob(token.split('.')[1]))
    
    expect(payload.org_id).toBeNull()
    expect(payload.role).toBe('LAWYER')
  })

  it('should store token in localStorage', () => {
    const mockToken = 'test-token-123'
    localStorage.setItem('token', mockToken)
    
    expect(localStorage.getItem('token')).toBe(mockToken)
    
    localStorage.clear()
  })
})

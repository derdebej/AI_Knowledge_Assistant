import { apiFetch } from './client'
import type { RegisterResponse, TokenResponse } from '../types/api'

export function register(
  email: string,
  password: string,
  fullName?: string,
): Promise<RegisterResponse> {
  return apiFetch<RegisterResponse>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, full_name: fullName || undefined }),
  })
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return apiFetch<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Not using vitest's `globals: true` (keeps tsconfig untouched), so
// React Testing Library's auto-cleanup-after-each never registers itself -
// wire it up explicitly instead.
afterEach(() => {
  cleanup()
})

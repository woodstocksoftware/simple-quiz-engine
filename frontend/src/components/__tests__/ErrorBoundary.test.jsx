import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ErrorBoundary from '../ErrorBoundary'

function ThrowingChild() {
  throw new Error('Test error')
}

describe('ErrorBoundary', () => {
  // Suppress expected console.error from React error boundary
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  test('renders children when no error', () => {
    render(
      <ErrorBoundary>
        <p>Hello</p>
      </ErrorBoundary>
    )
    expect(screen.getByText('Hello')).toBeInTheDocument()
  })

  test('renders error UI when child throws', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>
    )
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
  })

  test('calls onReset and recovers when reset button clicked', async () => {
    const onReset = vi.fn()
    render(
      <ErrorBoundary onReset={onReset}>
        <ThrowingChild />
      </ErrorBoundary>
    )
    await userEvent.click(screen.getByText('Return to Lobby'))
    expect(onReset).toHaveBeenCalledOnce()
  })
})

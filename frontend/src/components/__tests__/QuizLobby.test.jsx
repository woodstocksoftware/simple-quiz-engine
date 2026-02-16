import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import QuizLobby from '../QuizLobby'

const mockQuizzes = [
  { id: 'q1', title: 'Quiz One', description: 'First quiz', time_limit_seconds: 300 },
  { id: 'q2', title: 'Quiz Two', description: 'Second quiz', time_limit_seconds: 600 },
]

describe('QuizLobby', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  test('shows loading state initially', () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise(() => {}))
    render(<QuizLobby onStart={() => {}} />)
    expect(screen.getByText('Loading quizzes...')).toBeInTheDocument()
  })

  test('renders quiz list after fetch', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockQuizzes),
    })
    render(<QuizLobby onStart={() => {}} />)
    await waitFor(() => {
      expect(screen.getByText('Quiz One')).toBeInTheDocument()
    })
    expect(screen.getByText('Quiz Two')).toBeInTheDocument()
  })

  test('shows error message on fetch failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new Error('Network error'))
    render(<QuizLobby onStart={() => {}} />)
    await waitFor(() => {
      expect(screen.getByText('Could not load quizzes. Is the server running?')).toBeInTheDocument()
    })
  })

  test('selects a quiz when clicked', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockQuizzes),
    })
    render(<QuizLobby onStart={() => {}} />)
    await waitFor(() => {
      expect(screen.getByText('Quiz Two')).toBeInTheDocument()
    })
    // First quiz is selected by default; click second
    await userEvent.click(screen.getByText('Quiz Two'))
    const quizTwo = screen.getByText('Quiz Two').closest('[role="radio"]')
    expect(quizTwo).toHaveAttribute('aria-checked', 'true')
  })

  test('calls onStart with session id and token on form submit', async () => {
    const onStart = vi.fn()
    // First call: fetch quizzes
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockQuizzes),
      })
      // Second call: create session
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: 'session-1', token: 'tok-abc' }),
      })

    render(<QuizLobby onStart={onStart} />)
    await waitFor(() => {
      expect(screen.getByText('Quiz One')).toBeInTheDocument()
    })

    await userEvent.type(screen.getByLabelText('Your Name'), 'Alice')
    await userEvent.click(screen.getByText('Start Quiz'))

    await waitFor(() => {
      expect(onStart).toHaveBeenCalledWith('session-1', 'tok-abc')
    })
  })

  test('disables start button when no quiz is selected', () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise(() => {}))
    render(<QuizLobby onStart={() => {}} />)
    expect(screen.getByText('Start Quiz')).toBeDisabled()
  })
})

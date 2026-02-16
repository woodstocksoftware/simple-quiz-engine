import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import QuizResults from '../QuizResults'

const makeResults = (overrides = {}) => ({
  reason: 'submitted',
  score: { percentage: 80, correct: 4, earned: 4, possible: 5 },
  results: [
    { question_number: 1, question_text: 'Q1?', correct_answer: 'Yes', your_answer: 'Yes', is_correct: true, time_spent: 10 },
    { question_number: 2, question_text: 'Q2?', correct_answer: 'No', your_answer: 'Maybe', is_correct: false, time_spent: 5 },
  ],
  ...overrides,
})

describe('QuizResults', () => {
  test('displays score percentage', () => {
    render(<QuizResults results={makeResults()} onRetry={() => {}} />)
    expect(screen.getByText('80.0%')).toBeInTheDocument()
  })

  test('displays grade letter B for 80%', () => {
    const { container } = render(<QuizResults results={makeResults()} onRetry={() => {}} />)
    expect(container.querySelector('.grade').textContent).toBe('B')
  })

  test('displays grade letter A for 90%+', () => {
    const results = makeResults({ score: { percentage: 95, correct: 5, earned: 5, possible: 5 } })
    const { container } = render(<QuizResults results={results} onRetry={() => {}} />)
    expect(container.querySelector('.grade').textContent).toBe('A')
  })

  test('displays grade letter F for below 60%', () => {
    const results = makeResults({ score: { percentage: 40, correct: 2, earned: 2, possible: 5 } })
    const { container } = render(<QuizResults results={results} onRetry={() => {}} />)
    expect(container.querySelector('.grade').textContent).toBe('F')
  })

  test('shows time expired message when reason is time_expired', () => {
    render(<QuizResults results={makeResults({ reason: 'time_expired' })} onRetry={() => {}} />)
    expect(screen.getByText('Time expired')).toBeInTheDocument()
  })

  test('does not show time expired for normal submission', () => {
    render(<QuizResults results={makeResults()} onRetry={() => {}} />)
    expect(screen.queryByText('Time expired')).not.toBeInTheDocument()
  })

  test('renders question breakdown', () => {
    render(<QuizResults results={makeResults()} onRetry={() => {}} />)
    expect(screen.getByText(/Q1\?/)).toBeInTheDocument()
    expect(screen.getByText(/Q2\?/)).toBeInTheDocument()
  })

  test('calls onRetry when button clicked', async () => {
    const onRetry = vi.fn()
    render(<QuizResults results={makeResults()} onRetry={onRetry} />)
    await userEvent.click(screen.getByText('Try Another Quiz'))
    expect(onRetry).toHaveBeenCalledOnce()
  })
})

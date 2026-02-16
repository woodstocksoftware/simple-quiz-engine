import { useState, useEffect } from 'react'
import { API_URL } from '../config'
import { formatTime } from '../utils/formatTime'

function QuizLobby({ onStart }) {
  const [quizzes, setQuizzes] = useState([])
  const [selectedQuiz, setSelectedQuiz] = useState(null)
  const [studentName, setStudentName] = useState('')
  const [loading, setLoading] = useState(false)
  const [fetchLoading, setFetchLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setFetchLoading(true)
    setError(null)
    fetch(`${API_URL}/api/quizzes`)
      .then(res => {
        if (!res.ok) throw new Error('Failed to load quizzes')
        return res.json()
      })
      .then(data => {
        setQuizzes(data)
        if (data.length > 0) setSelectedQuiz(data[0])
      })
      .catch(() => setError('Could not load quizzes. Is the server running?'))
      .finally(() => setFetchLoading(false))
  }, [])

  const handleStart = async () => {
    if (!selectedQuiz) return

    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_URL}/api/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          quiz_id: selectedQuiz.id,
          student_name: studentName || 'Anonymous'
        })
      })
      if (!res.ok) throw new Error('Failed to create session')
      const session = await res.json()
      onStart(session.id, session.token)
    } catch {
      setError('Failed to start quiz. Please try again.')
      setLoading(false)
    }
  }

  const handleQuizCardKeyDown = (e, quiz) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      setSelectedQuiz(quiz)
    }
  }

  return (
    <div className="lobby">
      <h1>Quiz Engine</h1>

      <div className="lobby-form">
        {error && (
          <div className="error-banner" role="alert">
            <p>{error}</p>
            {!fetchLoading && quizzes.length === 0 && (
              <button className="retry-inline" onClick={() => window.location.reload()}>
                Retry
              </button>
            )}
          </div>
        )}

        <div className="form-group">
          <label htmlFor="student-name">Your Name</label>
          <input
            id="student-name"
            type="text"
            placeholder="Enter your name"
            value={studentName}
            onChange={(e) => setStudentName(e.target.value)}
            maxLength={200}
          />
        </div>

        <div className="form-group">
          <label id="quiz-select-label">Select Quiz</label>
          <div className="quiz-list" role="radiogroup" aria-labelledby="quiz-select-label">
            {fetchLoading && <p className="loading-text">Loading quizzes...</p>}
            {!fetchLoading && quizzes.length === 0 && !error && (
              <p className="empty-text">No quizzes available.</p>
            )}
            {quizzes.map(quiz => (
              <div
                key={quiz.id}
                role="radio"
                aria-checked={selectedQuiz?.id === quiz.id}
                tabIndex={0}
                className={`quiz-card ${selectedQuiz?.id === quiz.id ? 'selected' : ''}`}
                onClick={() => setSelectedQuiz(quiz)}
                onKeyDown={(e) => handleQuizCardKeyDown(e, quiz)}
              >
                <h3>{quiz.title}</h3>
                <p>{quiz.description}</p>
                <div className="quiz-meta">
                  <span>{formatTime(quiz.time_limit_seconds)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <button
          className="start-btn"
          onClick={handleStart}
          disabled={!selectedQuiz || loading}
        >
          {loading ? 'Starting...' : 'Start Quiz'}
        </button>
      </div>
    </div>
  )
}

export default QuizLobby

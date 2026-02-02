import { useState, useEffect } from 'react'

const API_URL = 'http://localhost:8000'

function QuizLobby({ onStart }) {
  const [quizzes, setQuizzes] = useState([])
  const [selectedQuiz, setSelectedQuiz] = useState(null)
  const [studentName, setStudentName] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetch(`${API_URL}/api/quizzes`)
      .then(res => res.json())
      .then(data => {
        setQuizzes(data)
        if (data.length > 0) setSelectedQuiz(data[0])
      })
      .catch(err => console.error('Failed to load quizzes:', err))
  }, [])

  const handleStart = async () => {
    if (!selectedQuiz) return
    
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/api/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          quiz_id: selectedQuiz.id,
          student_name: studentName || 'Anonymous'
        })
      })
      const session = await res.json()
      onStart(session.id)
    } catch (err) {
      console.error('Failed to create session:', err)
      setLoading(false)
    }
  }

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  return (
    <div className="lobby">
      <h1>📝 Quiz Engine</h1>
      
      <div className="lobby-form">
        <div className="form-group">
          <label>Your Name</label>
          <input
            type="text"
            placeholder="Enter your name"
            value={studentName}
            onChange={(e) => setStudentName(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label>Select Quiz</label>
          <div className="quiz-list">
            {quizzes.map(quiz => (
              <div 
                key={quiz.id}
                className={`quiz-card ${selectedQuiz?.id === quiz.id ? 'selected' : ''}`}
                onClick={() => setSelectedQuiz(quiz)}
              >
                <h3>{quiz.title}</h3>
                <p>{quiz.description}</p>
                <div className="quiz-meta">
                  <span>⏱️ {formatTime(quiz.time_limit_seconds)}</span>
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

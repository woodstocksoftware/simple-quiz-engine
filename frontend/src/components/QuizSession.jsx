import { useState, useEffect, useRef, useCallback } from 'react'

const WS_URL = 'ws://localhost:8000'

function QuizSession({ sessionId, onComplete }) {
  const [connected, setConnected] = useState(false)
  const [quiz, setQuiz] = useState(null)
  const [question, setQuestion] = useState(null)
  const [questionNumber, setQuestionNumber] = useState(0)
  const [totalQuestions, setTotalQuestions] = useState(0)
  const [timeRemaining, setTimeRemaining] = useState(0)
  const [selectedAnswer, setSelectedAnswer] = useState(null)
  const [answers, setAnswers] = useState({})
  const [started, setStarted] = useState(false)

  const ws = useRef(null)
  const onCompleteRef = useRef(onComplete)

  useEffect(() => {
    onCompleteRef.current = onComplete
  }, [onComplete])

  const handleMessage = useCallback((data) => {
    switch (data.type) {
      case 'connected':
        setQuiz(data.quiz)
        setTimeRemaining(data.session.time_remaining)
        setTotalQuestions(data.quiz.question_count)
        break
      case 'question':
        setQuestion(data.question)
        setQuestionNumber(data.question_number)
        setTotalQuestions(data.total_questions)
        setSelectedAnswer(data.existing_answer || null)
        break
      case 'timer_tick':
        setTimeRemaining(data.time_remaining)
        break
      case 'answer_received':
        break
      case 'quiz_complete':
        onCompleteRef.current(data)
        break
    }
  }, [])

  useEffect(() => {
    ws.current = new WebSocket(`${WS_URL}/ws/${sessionId}`)

    ws.current.onopen = () => {
      setConnected(true)
    }

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data)
      handleMessage(data)
    }

    ws.current.onclose = () => {
      setConnected(false)
    }

    ws.current.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    return () => {
      if (ws.current) ws.current.close()
    }
  }, [sessionId, handleMessage])

  const send = (message) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message))
    }
  }

  const handleStart = () => {
    send({ type: 'start_quiz' })
    setStarted(true)
  }

  const handleAnswer = (answer) => {
    setSelectedAnswer(answer)
    setAnswers(prev => ({ ...prev, [question.id]: answer }))
    send({ type: 'answer', question_id: question.id, answer })
  }

  const handleNext = () => send({ type: 'next_question', current: questionNumber })
  const handlePrev = () => send({ type: 'prev_question', current: questionNumber })
  const handleGoTo = (num) => send({ type: 'go_to_question', question_number: num })

  const handleSubmit = () => {
    if (confirm('Are you sure you want to submit?')) {
      send({ type: 'submit_quiz' })
    }
  }

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  if (!connected) return <div className="loading">Connecting...</div>

  if (!started) {
    return (
      <div className="pre-quiz">
        <h1>{quiz?.title}</h1>
        <p>{quiz?.description}</p>
        <div className="quiz-info">
          <p>{totalQuestions} questions</p>
          <p>{formatTime(timeRemaining)} time limit</p>
        </div>
        <button className="start-btn" onClick={handleStart}>Begin Quiz</button>
      </div>
    )
  }

  return (
    <div className="quiz-session">
      <div className="quiz-header">
        <div className="quiz-title">{quiz?.title}</div>
        <div className={`timer ${timeRemaining < 60 ? 'warning' : ''}`}>
          {formatTime(timeRemaining)}
        </div>
      </div>

      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${(questionNumber / totalQuestions) * 100}%` }} />
      </div>

      <div className="question-nav">
        {Array.from({ length: totalQuestions }, (_, i) => (
          <button
            key={i + 1}
            className={`nav-btn ${questionNumber === i + 1 ? 'current' : ''} ${answers[`q${i + 1}`] ? 'answered' : ''}`}
            onClick={() => handleGoTo(i + 1)}
          >
            {i + 1}
          </button>
        ))}
      </div>

      {question && (
        <div className="question-container">
          <div className="question-header">Question {questionNumber} of {totalQuestions}</div>
          <div className="question-text">{question.text}</div>
          <div className="options">
            {question.options.map((option, index) => (
              <button
                key={index}
                className={`option ${selectedAnswer === option ? 'selected' : ''}`}
                onClick={() => handleAnswer(option)}
              >
                <span className="option-letter">{String.fromCharCode(65 + index)}</span>
                {option}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="quiz-footer">
        <button className="nav-btn-large" onClick={handlePrev} disabled={questionNumber <= 1}>
          Previous
        </button>
        {questionNumber < totalQuestions ? (
          <button className="nav-btn-large primary" onClick={handleNext}>Next</button>
        ) : (
          <button className="nav-btn-large submit" onClick={handleSubmit}>Submit Quiz</button>
        )}
      </div>
    </div>
  )
}

export default QuizSession

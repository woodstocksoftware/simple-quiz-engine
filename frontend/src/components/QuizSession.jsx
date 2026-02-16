import { useState, useEffect, useRef, useCallback } from 'react'
import { WS_URL } from '../config'
import { formatTime } from '../utils/formatTime'

const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_BASE_DELAY = 1000

function QuizSession({ sessionId, sessionToken, onComplete }) {
  const [connected, setConnected] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)
  const [quiz, setQuiz] = useState(null)
  const [question, setQuestion] = useState(null)
  const [questionNumber, setQuestionNumber] = useState(0)
  const [totalQuestions, setTotalQuestions] = useState(0)
  const [timeRemaining, setTimeRemaining] = useState(0)
  const [selectedAnswer, setSelectedAnswer] = useState(null)
  const [answeredNumbers, setAnsweredNumbers] = useState(new Set())
  const [started, setStarted] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [answerSaved, setAnswerSaved] = useState(false)
  const [maxAttemptsReached, setMaxAttemptsReached] = useState(false)

  const ws = useRef(null)
  const onCompleteRef = useRef(onComplete)
  const reconnectAttempts = useRef(0)
  const intentionalClose = useRef(false)
  const answerSavedTimer = useRef(null)
  const currentQuestionNumberRef = useRef(0)
  const connectWsRef = useRef(null)

  useEffect(() => {
    onCompleteRef.current = onComplete
  }, [onComplete])

  useEffect(() => {
    currentQuestionNumberRef.current = questionNumber
  }, [questionNumber])

  const handleMessage = useCallback((data) => {
    switch (data.type) {
      case 'connected':
        setQuiz(data.quiz)
        setTimeRemaining(data.session.time_remaining)
        setTotalQuestions(data.quiz.question_count)
        if (data.session.status === 'in_progress') {
          setStarted(true)
        }
        break
      case 'question':
        setQuestion(data.question)
        setQuestionNumber(data.question_number)
        setTotalQuestions(data.total_questions)
        setSelectedAnswer(data.existing_answer || null)
        if (data.existing_answer) {
          setAnsweredNumbers(prev => new Set([...prev, data.question_number]))
        }
        setStarted(true)
        break
      case 'timer_tick':
        setTimeRemaining(data.time_remaining)
        break
      case 'answer_received':
        setAnsweredNumbers(prev => new Set([...prev, currentQuestionNumberRef.current]))
        setAnswerSaved(true)
        break
      case 'quiz_complete':
        intentionalClose.current = true
        onCompleteRef.current(data)
        break
      case 'error':
        break
    }
  }, [])

  const connectWs = useCallback(() => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) return

    const url = `${WS_URL}/ws/${sessionId}?token=${encodeURIComponent(sessionToken || '')}`
    ws.current = new WebSocket(url)

    ws.current.onopen = () => {
      setConnected(true)
      setReconnecting(false)
      reconnectAttempts.current = 0
    }

    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        handleMessage(data)
      } catch {
        // Ignore malformed messages
      }
    }

    ws.current.onclose = () => {
      setConnected(false)
      if (!intentionalClose.current && reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
        setReconnecting(true)
        const delay = RECONNECT_BASE_DELAY * Math.pow(2, reconnectAttempts.current)
        reconnectAttempts.current += 1
        setTimeout(() => connectWsRef.current?.(), delay)
      } else if (reconnectAttempts.current >= MAX_RECONNECT_ATTEMPTS) {
        setMaxAttemptsReached(true)
      }
    }

    ws.current.onerror = () => {}
  }, [sessionId, sessionToken, handleMessage])

  // Keep ref in sync with latest connectWs
  useEffect(() => {
    connectWsRef.current = connectWs
  }, [connectWs])

  useEffect(() => {
    intentionalClose.current = false
    connectWs()
    return () => {
      intentionalClose.current = true
      if (ws.current) ws.current.close()
    }
  }, [connectWs])

  // Warn before leaving during active quiz
  useEffect(() => {
    if (!started) return
    const handler = (e) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [started])

  // Auto-hide answer saved indicator
  useEffect(() => {
    if (answerSaved) {
      if (answerSavedTimer.current) clearTimeout(answerSavedTimer.current)
      answerSavedTimer.current = setTimeout(() => setAnswerSaved(false), 1500)
    }
    return () => { if (answerSavedTimer.current) clearTimeout(answerSavedTimer.current) }
  }, [answerSaved])

  const send = (message) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message))
    }
  }

  const handleStart = () => {
    send({ type: 'start_quiz' })
  }

  const handleAnswer = (answer) => {
    setSelectedAnswer(answer)
    setAnswerSaved(false)
    send({ type: 'answer', question_id: question.id, answer })
  }

  const handleNext = () => send({ type: 'next_question', current: questionNumber })
  const handlePrev = () => send({ type: 'prev_question', current: questionNumber })
  const handleGoTo = (num) => send({ type: 'go_to_question', question_number: num })

  const handleSubmit = () => setShowConfirm(true)
  const confirmSubmit = () => {
    setShowConfirm(false)
    send({ type: 'submit_quiz' })
  }

  const warningThreshold = quiz
    ? Math.max(30, Math.min(120, Math.round(quiz.time_limit_seconds * 0.2)))
    : 60

  if (!connected && !reconnecting) return <div className="loading">Connecting...</div>
  if (reconnecting) {
    return (
      <div className="loading">
        <p>Connection lost. Reconnecting...</p>
        {maxAttemptsReached && (
          <button className="start-btn" onClick={() => { reconnectAttempts.current = 0; setMaxAttemptsReached(false); connectWs() }}>
            Retry
          </button>
        )}
      </div>
    )
  }

  if (!started) {
    return (
      <div className="pre-quiz">
        <h1>{quiz?.title}</h1>
        <p>{quiz?.description}</p>
        <div className="quiz-info" role="group" aria-label="Quiz information">
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
        <div
          className={`timer ${timeRemaining < warningThreshold ? 'warning' : ''}`}
          role="timer"
          aria-live="off"
          aria-label={`Time remaining: ${formatTime(timeRemaining)}`}
        >
          {formatTime(timeRemaining)}
        </div>
      </div>

      {timeRemaining === warningThreshold && (
        <div className="sr-only" aria-live="assertive">
          Warning: {formatTime(warningThreshold)} remaining
        </div>
      )}

      <div
        className="progress-bar"
        role="progressbar"
        aria-valuenow={questionNumber}
        aria-valuemin={1}
        aria-valuemax={totalQuestions}
        aria-label={`Question ${questionNumber} of ${totalQuestions}`}
      >
        <div className="progress-fill" style={{ width: `${(questionNumber / totalQuestions) * 100}%` }} />
      </div>

      <div className="question-nav" role="group" aria-label="Question navigation">
        {Array.from({ length: totalQuestions }, (_, i) => {
          const qNum = i + 1
          const isCurrent = questionNumber === qNum
          const isAnswered = answeredNumbers.has(qNum)
          return (
            <button
              key={qNum}
              className={`nav-btn ${isCurrent ? 'current' : ''} ${isAnswered ? 'answered' : ''}`}
              onClick={() => handleGoTo(qNum)}
              aria-label={`Question ${qNum}${isCurrent ? ' (current)' : ''}${isAnswered ? ' (answered)' : ''}`}
              aria-current={isCurrent ? 'step' : undefined}
            >
              {qNum}
            </button>
          )
        })}
      </div>

      {question && (
        <div className="question-container">
          <div className="question-header" id="question-heading">
            Question {questionNumber} of {totalQuestions}
          </div>
          <div className="question-text" id="question-text">{question.text}</div>
          <div className="options" role="radiogroup" aria-labelledby="question-text">
            {question.options.map((option, index) => (
              <button
                key={index}
                className={`option ${selectedAnswer === option ? 'selected' : ''}`}
                onClick={() => handleAnswer(option)}
                role="radio"
                aria-checked={selectedAnswer === option}
              >
                <span className="option-letter" aria-hidden="true">
                  {String.fromCharCode(65 + index)}
                </span>
                {option}
              </button>
            ))}
          </div>
          {answerSaved && (
            <div className="answer-saved" aria-live="polite">Answer saved</div>
          )}
        </div>
      )}

      <div className="quiz-footer">
        <button
          className="nav-btn-large"
          onClick={handlePrev}
          disabled={questionNumber <= 1}
          aria-label="Previous question"
        >
          Previous
        </button>
        {questionNumber < totalQuestions ? (
          <button className="nav-btn-large primary" onClick={handleNext} aria-label="Next question">
            Next
          </button>
        ) : (
          <button className="nav-btn-large submit" onClick={handleSubmit}>
            Submit Quiz
          </button>
        )}
      </div>

      {started && questionNumber < totalQuestions && (
        <div className="early-submit">
          <button className="early-submit-btn" onClick={handleSubmit}>
            Submit Quiz Early
          </button>
        </div>
      )}

      {showConfirm && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Confirm submission">
          <div className="modal">
            <h2>Submit Quiz?</h2>
            <p>Are you sure you want to submit? You cannot change your answers after submitting.</p>
            <div className="modal-actions">
              <button className="modal-btn cancel" onClick={() => setShowConfirm(false)}>
                Cancel
              </button>
              <button className="modal-btn confirm" onClick={confirmSubmit} autoFocus>
                Submit
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default QuizSession

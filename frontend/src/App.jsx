import { useState } from 'react'
import QuizLobby from './components/QuizLobby'
import QuizSession from './components/QuizSession'
import QuizResults from './components/QuizResults'
import ErrorBoundary from './components/ErrorBoundary'
import './App.css'

const SESSION_KEY = 'quiz_session'

function getSavedSession() {
  try {
    const saved = sessionStorage.getItem(SESSION_KEY)
    if (saved) {
      const { id, token } = JSON.parse(saved)
      if (id && token) return { id, token }
    }
  } catch {
    sessionStorage.removeItem(SESSION_KEY)
  }
  return null
}

function App() {
  const saved = getSavedSession()
  const [screen, setScreen] = useState(saved ? 'quiz' : 'lobby')
  const [sessionId, setSessionId] = useState(saved?.id ?? null)
  const [sessionToken, setSessionToken] = useState(saved?.token ?? null)
  const [results, setResults] = useState(null)

  const handleStartQuiz = (newSessionId, token) => {
    setSessionId(newSessionId)
    setSessionToken(token)
    setScreen('quiz')
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({ id: newSessionId, token }))
  }

  const handleQuizComplete = (quizResults) => {
    setResults(quizResults)
    setScreen('results')
    sessionStorage.removeItem(SESSION_KEY)
  }

  const handleRetry = () => {
    setSessionId(null)
    setSessionToken(null)
    setResults(null)
    setScreen('lobby')
    sessionStorage.removeItem(SESSION_KEY)
  }

  return (
    <ErrorBoundary onReset={handleRetry}>
      <div className="app">
        {screen === 'lobby' && (
          <QuizLobby onStart={handleStartQuiz} />
        )}
        {screen === 'quiz' && sessionId && (
          <QuizSession
            sessionId={sessionId}
            sessionToken={sessionToken}
            onComplete={handleQuizComplete}
          />
        )}
        {screen === 'results' && results && (
          <QuizResults
            results={results}
            onRetry={handleRetry}
          />
        )}
      </div>
    </ErrorBoundary>
  )
}

export default App

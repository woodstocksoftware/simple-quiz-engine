import { useState } from 'react'
import QuizLobby from './components/QuizLobby'
import QuizSession from './components/QuizSession'
import QuizResults from './components/QuizResults'
import './App.css'

function App() {
  const [screen, setScreen] = useState('lobby')
  const [sessionId, setSessionId] = useState(null)
  const [results, setResults] = useState(null)

  const handleStartQuiz = (newSessionId) => {
    setSessionId(newSessionId)
    setScreen('quiz')
  }

  const handleQuizComplete = (quizResults) => {
    setResults(quizResults)
    setScreen('results')
  }

  const handleRetry = () => {
    setSessionId(null)
    setResults(null)
    setScreen('lobby')
  }

  return (
    <div className="app">
      {screen === 'lobby' && (
        <QuizLobby onStart={handleStartQuiz} />
      )}
      {screen === 'quiz' && sessionId && (
        <QuizSession 
          sessionId={sessionId} 
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
  )
}

export default App

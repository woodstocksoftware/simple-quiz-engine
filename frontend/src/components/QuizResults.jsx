function QuizResults({ results, onRetry }) {
  const { score, results: questions, reason } = results
  
  const getGrade = (percentage) => {
    if (percentage >= 90) return { letter: 'A', color: '#22c55e' }
    if (percentage >= 80) return { letter: 'B', color: '#84cc16' }
    if (percentage >= 70) return { letter: 'C', color: '#eab308' }
    if (percentage >= 60) return { letter: 'D', color: '#f97316' }
    return { letter: 'F', color: '#ef4444' }
  }
  
  const grade = getGrade(score.percentage)

  return (
    <div className="results">
      <div className="results-header">
        <h1>Quiz Complete!</h1>
        {reason === 'time_expired' && <p className="time-warning">⏱️ Time expired</p>}
      </div>

      <div className="score-card">
        <div className="grade" style={{ backgroundColor: grade.color }}>{grade.letter}</div>
        <div className="score-details">
          <div className="percentage">{score.percentage.toFixed(1)}%</div>
          <div className="fraction">{score.correct} / {questions.length} correct</div>
          <div className="points">{score.earned} / {score.possible} points</div>
        </div>
      </div>

      <div className="results-breakdown">
        <h2>Question Breakdown</h2>
        {questions.map((q, index) => (
          <div key={index} className={`result-item ${q.is_correct ? 'correct' : 'incorrect'}`}>
            <div className="result-icon">{q.is_correct ? '✓' : '✗'}</div>
            <div className="result-content">
              <div className="result-question"><strong>Q{q.question_number}:</strong> {q.question_text}</div>
              <div className="result-answers">
                <span className="your-answer">Your answer: <strong>{q.your_answer || 'No answer'}</strong></span>
                {!q.is_correct && <span className="correct-answer">Correct: <strong>{q.correct_answer}</strong></span>}
              </div>
              <div className="result-time">⏱️ {q.time_spent}s</div>
            </div>
          </div>
        ))}
      </div>

      <button className="retry-btn" onClick={onRetry}>Try Another Quiz</button>
    </div>
  )
}

export default QuizResults

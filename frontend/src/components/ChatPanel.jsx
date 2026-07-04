import React, { useState, useRef, useEffect } from 'react'

export default function ChatPanel({ messages, loading, onAsk, samples, gaps, contradictions }) {
  const [input, setInput] = useState('')
  const endRef = useRef(null)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, loading])

  function submit(e) {
    e.preventDefault()
    onAsk(input)
    setInput('')
  }

  return (
    <div className="chat">
      <div className="messages">
        {messages.length === 0 && (
          <div className="welcome">
            <h2>Спросите о материалах, процессах, экспериментах</h2>
            <p>Естественным языком, на RU или EN. Примеры:</p>
            <div className="samples">
              {samples.map((q, i) => (
                <button key={i} className="sample" onClick={() => onAsk(q)}>{q}</button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div className="bubble">
              <div className="text">{m.text}</div>
              {m.citations?.length > 0 && (
                <div className="citations">
                  {m.citations.map((c, j) => (
                    <div key={j} className="cite" title={c.snippet}>
                      <span className="cite-src">{c.source}</span>
                      <span className="cite-conf">{Math.round(c.confidence * 100)}%</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && <div className="msg assistant"><div className="bubble typing">анализирую граф и источники…</div></div>}
        <div ref={endRef} />
      </div>

      {(gaps?.length > 0 || contradictions?.length > 0) && (
        <div className="insights">
          {contradictions?.length > 0 && (
            <div className="insight-block contra">
              <div className="insight-title">⚠ Противоречия ({contradictions.length})</div>
              {contradictions.slice(0, 4).map((c, i) => <div key={i} className="insight-item">{c}</div>)}
            </div>
          )}
          {gaps?.length > 0 && (
            <div className="insight-block gap">
              <div className="insight-title">◌ Пробелы в знаниях ({gaps.length})</div>
              {gaps.slice(0, 4).map((g, i) => <div key={i} className="insight-item">{g}</div>)}
            </div>
          )}
        </div>
      )}

      <form className="composer" onSubmit={submit}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Задайте вопрос…"
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>→</button>
      </form>
    </div>
  )
}

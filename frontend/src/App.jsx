import React, { useState, useEffect } from 'react'
import { ask, stats, expandNode } from './api'
import GraphPanel from './components/GraphPanel'
import ChatPanel from './components/ChatPanel'

const SAMPLE_QS = [
  'Какие методы обессоливания воды подходят при сульфатах 200–300 мг/л и сухом остатке ≤1000 мг/дм³?',
  'Какая скорость циркуляции католита при электроэкстракции никеля считается оптимальной?',
  'Покажи распределение Au, Ag и МПГ между штейном и шлаком',
]

export default function App() {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [graph, setGraph] = useState({ nodes: [], edges: [] })
  const [gaps, setGaps] = useState([])
  const [contradictions, setContradictions] = useState([])
  const [dbStats, setDbStats] = useState(null)

  useEffect(() => { stats().then(setDbStats).catch(() => {}) }, [])

  async function handleAsk(question) {
    if (!question.trim() || loading) return
    setMessages((m) => [...m, { role: 'user', text: question }])
    setLoading(true)
    try {
      const r = await ask(question)
      setMessages((m) => [...m, { role: 'assistant', text: r.answer, citations: r.citations }])
      setGraph(mergeGraph(r.graph))
      setGaps(r.gaps || [])
      setContradictions(r.contradictions || [])
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', text: `Ошибка: ${e.message}` }])
    } finally {
      setLoading(false)
    }
  }

  async function handleNodeClick(node) {
    try {
      const sub = await expandNode(node.id)
      setGraph((g) => mergeGraph(sub, g))
    } catch (e) { /* ignore */ }
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">◇</span> SciGraph
          <span className="tagline">R&D карта знаний · горно-металлургия</span>
        </div>
        {dbStats?.graph && (
          <div className="stats">
            узлов: {dbStats.graph.nodes ?? '—'} · связей: {dbStats.graph.relations ?? '—'} · векторов: {dbStats.vectors ?? '—'}
          </div>
        )}
      </header>

      <div className="split">
        <section className="left">
          <ChatPanel
            messages={messages}
            loading={loading}
            onAsk={handleAsk}
            samples={SAMPLE_QS}
            gaps={gaps}
            contradictions={contradictions}
          />
        </section>
        <section className="right">
          <GraphPanel data={graph} onNodeClick={handleNodeClick} />
        </section>
      </div>
    </div>
  )
}

function mergeGraph(incoming, existing = { nodes: [], edges: [] }) {
  const nodeMap = new Map(existing.nodes.map((n) => [n.id, n]))
  for (const n of incoming.nodes || []) nodeMap.set(n.id, n)
  const edgeKey = (e) => `${e.source}->${e.target}:${e.type}`
  const edgeMap = new Map(existing.edges.map((e) => [edgeKey(e), e]))
  for (const e of incoming.edges || []) edgeMap.set(edgeKey(e), e)
  return { nodes: [...nodeMap.values()], edges: [...edgeMap.values()] }
}

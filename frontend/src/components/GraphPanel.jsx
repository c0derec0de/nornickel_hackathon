import React, { useRef, useMemo } from 'react'
import ForceGraph2D from 'react-force-graph-2d'

const TYPE_COLORS = {
  Material: '#4ade80', Process: '#60a5fa', Equipment: '#f59e0b',
  Property: '#a78bfa', Condition: '#f472b6', Experiment: '#22d3ee',
  Publication: '#94a3b8', Expert: '#fb7185', Facility: '#fbbf24',
  Finding: '#34d399', Geography: '#c084fc', Entity: '#64748b',
}

export default function GraphPanel({ data, onNodeClick }) {
  const fgRef = useRef()

  const graphData = useMemo(() => ({
    nodes: (data.nodes || []).map((n) => ({ id: n.id, label: n.label, type: n.type })),
    links: (data.edges || []).map((e) => ({ source: e.source, target: e.target, type: e.type })),
  }), [data])

  const empty = graphData.nodes.length === 0

  return (
    <div className="graph-wrap">
      <div className="graph-legend">
        {Object.entries(TYPE_COLORS).filter(([t]) => t !== 'Entity').map(([t, c]) => (
          <span key={t} className="legend-item"><i style={{ background: c }} />{t}</span>
        ))}
      </div>
      {empty ? (
        <div className="graph-empty">Граф связей появится здесь после запроса</div>
      ) : (
        <ForceGraph2D
          ref={fgRef}
          graphData={graphData}
          backgroundColor="#0b0f17"
          nodeRelSize={5}
          linkColor={() => 'rgba(148,163,184,0.35)'}
          linkDirectionalArrowLength={3}
          linkDirectionalArrowRelPos={1}
          onNodeClick={onNodeClick}
          nodeCanvasObject={(node, ctx, scale) => {
            const r = 5
            ctx.beginPath()
            ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
            ctx.fillStyle = TYPE_COLORS[node.type] || TYPE_COLORS.Entity
            ctx.fill()
            const label = node.label || node.id
            const fontSize = Math.max(10 / scale, 3)
            ctx.font = `${fontSize}px Inter, sans-serif`
            ctx.fillStyle = '#e2e8f0'
            ctx.textAlign = 'center'
            ctx.fillText(label.length > 22 ? label.slice(0, 22) + '…' : label, node.x, node.y + r + fontSize + 1)
          }}
        />
      )}
    </div>
  )
}

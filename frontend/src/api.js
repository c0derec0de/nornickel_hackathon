const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export async function ask(question, filters = {}) {
  const res = await fetch(`${BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, ...filters }),
  })
  if (!res.ok) throw new Error(`API ${res.status}`)
  return res.json()
}

export async function stats() {
  const res = await fetch(`${BASE}/stats`)
  return res.json()
}

export async function expandNode(entity) {
  const res = await fetch(`${BASE}/graph?entity=${encodeURIComponent(entity)}&depth=2`)
  return res.json()
}

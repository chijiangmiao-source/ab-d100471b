// Thin client for the contraction API.  Same-origin in production (proxied
// by the web server), same paths in dev (proxied by Vite).

export async function fetchInfo() {
  const r = await fetch('/api/info')
  if (!r.ok) throw new Error(`info ${r.status}`)
  return r.json()
}

export async function postContract(payload) {
  const r = await fetch('/api/contract', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) {
    return {
      ok: false,
      errors: [
        {
          code: 'http_error',
          loc: '',
          message: `服务返回 HTTP ${r.status}`,
        },
      ],
    }
  }
  return r.json()
}

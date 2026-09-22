import React, { useMemo } from 'react'

// Index ledger: for every network index show its dimension, how often it
// occurs, which tensors carry it, and whether it is an open leg (occurs once)
// or a bond contracted between two tensors (occurs twice).
export default function IndexTable({ result }) {
  const rows = useMemo(() => {
    const owners = new Map()
    for (const t of result.inputs) {
      for (const idx of t.indices) {
        if (!owners.has(idx)) owners.set(idx, [])
        owners.get(idx).push(t.name)
      }
    }
    return Object.entries(result.dimensions)
      .map(([idx, dim]) => {
        const who = owners.get(idx) || []
        return { idx, dim, who, kind: who.length === 1 ? 'open' : 'bond' }
      })
      .sort((a, b) => a.idx.localeCompare(b.idx))
  }, [result])

  return (
    <div className="index-table">
      <h3 className="mt">指标清单</h3>
      <table>
        <thead>
          <tr>
            <th>指标</th>
            <th>维数</th>
            <th>类型</th>
            <th>出现</th>
            <th>所属张量</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.idx}>
              <td><code>{r.idx}</code></td>
              <td>{r.dim}</td>
              <td>
                <span className={`occ ${r.kind}`}>
                  {r.kind === 'open' ? '开指标（保留）' : '收缩边'}
                </span>
              </td>
              <td>{r.who.length} 次</td>
              <td>{r.who.join(' , ')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

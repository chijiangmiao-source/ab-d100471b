import React, { useEffect, useMemo, useState } from 'react'
import { fetchInfo, postContract } from './api.js'
import TreeDiagram from './components/TreeDiagram.jsx'
import CutsPanel from './components/CutsPanel.jsx'
import IndexTable from './components/IndexTable.jsx'
import { RING4_SAMPLE, STAR_SAMPLE } from './samples.js'

const splitTokens = (text) => text.split(/[\s,]+/).filter(Boolean)

export default function App() {
  const [tensors, setTensors] = useState([
    { name: 'A', indexText: 'i j' },
    { name: 'B', indexText: 'j k' },
    { name: 'C', indexText: 'k l' },
    { name: 'D', indexText: 'l i' },
  ])
  const [dims, setDims] = useState(
    ['i', 'j', 'k', 'l'].map((name) => ({ name, dim: '2' })),
  )
  const [result, setResult] = useState(null)
  const [errors, setErrors] = useState([])
  const [busy, setBusy] = useState(false)
  const [apiUp, setApiUp] = useState(null)
  const [info, setInfo] = useState(null)

  useEffect(() => {
    fetchInfo()
      .then((i) => {
        setInfo(i)
        setApiUp(true)
      })
      .catch(() => setApiUp(false))
  }, [])

  // index -> {first, positions: Set of "tensor#j"]} for highlighting
  const indexUsage = useMemo(() => {
    const map = new Map()
    tensors.forEach((t, ti) => {
      splitTokens(t.indexText).forEach((idx, j) => {
        if (!map.has(idx)) map.set(idx, [])
        map.get(idx).push({ ti, j })
      })
    })
    return map
  }, [tensors])

  const errorMap = useMemo(() => buildErrorMap(errors), [errors])

  function updateTensor(ti, patch) {
    setTensors((ts) => ts.map((t, k) => (k === ti ? { ...t, ...patch } : t)))
  }
  function addTensor() {
    if (tensors.length >= 11) return
    setTensors((ts) => [...ts, { name: nextName(ts), indexText: '' }])
  }
  function removeTensor(ti) {
    setTensors((ts) => ts.filter((_, k) => k !== ti))
  }
  function updateDim(di, patch) {
    setDims((ds) => ds.map((d, k) => (k === di ? { ...d, ...patch } : d)))
  }
  function addDim() {
    setDims((ds) => [...ds, { name: '', dim: '2' }])
  }
  function removeDim(di) {
    setDims((ds) => ds.filter((_, k) => k !== di))
  }
  function syncDims() {
    setDims((ds) => {
      const known = new Map(ds.map((d) => [d.name, d.dim]))
      const merged = []
      for (const idx of indexUsage.keys()) {
        merged.push({ name: idx, dim: known.get(idx) ?? '2' })
      }
      for (const d of ds) if (!indexUsage.has(d.name)) merged.push(d)
      return merged
    })
  }

  async function submit() {
    setBusy(true)
    const payload = {
      tensors: tensors.map((t) => ({
        name: t.name,
        indices: splitTokens(t.indexText),
      })),
      dimensions: Object.fromEntries(
        dims
          .filter((d) => d.name.trim() !== '')
          .map((d) => [d.name.trim(), /^\d+$/.test(d.dim) ? Number(d.dim) : d.dim]),
      ),
    }
    const body = await postContract(payload)
    setBusy(false)
    if (body.ok) {
      setResult(body)
      setErrors([])
    } else {
      // preserve the user's input; only surface the located errors
      setResult(null)
      setErrors(body.errors || [])
    }
  }

  function loadSample(sample) {
    setTensors(sample.tensors.map((t) => ({ ...t })))
    setDims(sample.dims.map((d) => ({ ...d })))
    setResult(null)
    setErrors([])
  }

  return (
    <div className="page">
      <header>
        <h1>张量网络收缩计划器</h1>
        <p className="sub">
          精确枚举收缩树 · 先最小化峰值内存，再最小化总乘法数 · 同优解按规范括号串确定
        </p>
        <span className={`pill ${apiUp ? 'ok' : apiUp === false ? 'bad' : ''}`}>
          API {apiUp ? '在线' : apiUp === false ? '不可达' : '检测中…'}
        </span>
      </header>

      {errors.length > 0 && (
        <div className="banner bad" role="alert">
          <strong>输入未通过校验（已保留你的输入）：</strong>
          <ul>
            {errors.map((e, i) => (
              <li key={i}>
                <code>{e.loc || '/'}</code> {e.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      <main className="grid">
        <section className="card">
          <div className="card-head">
            <h2>① 张量与指标</h2>
            <div className="row">
              <button onClick={() => loadSample(RING4_SAMPLE)}>四张量环示例</button>
              <button onClick={() => loadSample(STAR_SAMPLE)}>星形贪心陷阱</button>
            </div>
          </div>
          <p className="hint">
            每个张量 1–6 个互异 ASCII 指标；全网 2–11 个唯一张量，指标出现 1 或 2
            次，网络须连通。
          </p>

          <div className="tensor-list">
            {tensors.map((t, ti) => (
              <div
                key={ti}
                className={`tensor ${errorMap.tensor[ti]?.has('') ? 'has-err' : ''}`}
              >
                <input
                  className={`name ${errorMap.tensor[ti]?.has('name') ? 'err' : ''}`}
                  value={t.name}
                  placeholder="名称"
                  onChange={(e) => updateTensor(ti, { name: e.target.value })}
                />
                <span className="paren">(</span>
                <input
                  className={`indices ${
                    errorMap.tensor[ti]?.has('indices') ||
                    errorMap.tensor[ti]?.has('indicesAny')
                      ? 'err'
                      : ''
                  }`}
                  value={t.indexText}
                  placeholder="a b c"
                  onChange={(e) =>
                    updateTensor(ti, { indexText: e.target.value })
                  }
                />
                <span className="paren">)</span>
                <button className="ghost" onClick={() => removeTensor(ti)}>
                  ✕
                </button>
                <IndexTokenHints ti={ti} text={t.indexText} errorMap={errorMap} />
              </div>
            ))}
          </div>
          <div className="row">
            <button onClick={addTensor} disabled={tensors.length >= 11}>
              ＋ 添加张量 ({tensors.length}/11)
            </button>
          </div>

          <h2 className="mt">② 指标维数</h2>
          <div className="dim-list">
            {dims.map((d, di) => {
              const key = d.name.trim()
              const occurrences = indexUsage.get(key)?.length ?? 0
              const flagged = errorMap.dim.has(key)
              return (
                <div key={di} className={`dim ${flagged ? 'has-err' : ''}`}>
                  <input
                    className={`name ${flagged ? 'err' : ''}`}
                    value={d.name}
                    placeholder="索引"
                    onChange={(e) => updateDim(di, { name: e.target.value })}
                  />
                  <span className="dim-sep">维数</span>
                  <input
                    className={`dimval ${flagged ? 'err' : ''}`}
                    value={d.dim}
                    onChange={(e) => updateDim(di, { dim: e.target.value })}
                  />
                  <span
                    className={`occ ${occurrences === 0 ? 'zero' : occurrences === 1 ? 'open' : 'bond'}`}
                    title="该指标在全网出现次数"
                  >
                    {occurrences === 1 ? '开指标' : occurrences === 2 ? '收缩边' : '未使用'}
                  </span>
                  <button className="ghost" onClick={() => removeDim(di)}>
                    ✕
                  </button>
                </div>
              )
            })}
          </div>
          <div className="row">
            <button onClick={addDim}>＋ 添加维数</button>
            <button onClick={syncDims}>⇄ 按张量索引补齐</button>
            <button className="primary" onClick={submit} disabled={busy}>
              {busy ? '计算中…' : '提交收缩计划'}
            </button>
          </div>
        </section>

        <Results result={result} />
      </main>

      <footer>
        {info ? (
          <span>
            约束：张量 {info.limits.tensors[0]}–{info.limits.tensors[1]} ·
            指标/张量 {info.limits.indices_per_tensor[0]}–
            {info.limits.indices_per_tensor[1]} · 维数{' '}
            {info.limits.dimension[0]}–{info.limits.dimension[1]}
          </span>
        ) : null}
      </footer>
    </div>
  )
}

function Results({ result }) {
  if (!result) {
    return (
      <section className="card placeholder">
        <h2>结论</h2>
        <p>提交合法网络后，这里将展示规范收缩树、指标与根切分分类证据。</p>
      </section>
    )
  }
  const m = result.metrics
  return (
    <section className="card results">
      <h2>③ 优化结论</h2>
      <div className="metrics">
        <Metric label="峰值元素数（输入+中间量）" value={m.peak_elements} accent />
        <Metric label="总乘法数" value={m.total_multiplications} />
        <Metric label="最优树数量" value={m.optimal_tree_count} />
        <Metric label="结果张量大小" value={m.result_size} />
      </div>
      <div className="canon">
        <span className="muted">规范收缩括号：</span>
        <code>{result.canonical}</code>
      </div>
      <p className="muted small">
        结果保留指标：
        {m.result_indices.length ? m.result_indices.join(', ') : '无（缩成标量）'}
        {' ｜ 所有输入元素合计：'}
        {m.input_elements}
      </p>

      <h3 className="mt">收缩树图</h3>
      <TreeDiagram result={result} />

      <IndexTable result={result} />

      <CutsPanel result={result} />
    </section>
  )
}

function Metric({ label, value, accent }) {
  return (
    <div className={`metric ${accent ? 'accent' : ''}`}>
      <div className="value">{value}</div>
      <div className="label">{label}</div>
    </div>
  )
}

function IndexTokenHints({ ti, text, errorMap }) {
  const tokens = splitTokens(text)
  const bad = errorMap.tensor[ti]
  if (!bad || ![...bad].some((k) => typeof k === 'number')) return null
  return (
    <div className="token-hints">
      {tokens.map((tok, j) =>
        bad.has(j) ? <span key={j} className="tok-err">ⓧ{tok}</span> : null,
      )}
    </div>
  )
}

function buildErrorMap(errors) {
  const map = { tensor: {}, dim: new Set() }
  for (const e of errors) {
    const loc = e.loc || ''
    const tm = loc.match(/^\/tensors\/(\d+)(?:\/(name|indices)(?:\/(\d+))?)?/)
    if (tm) {
      const ti = Number(tm[1])
      const field = tm[2]
      const idx = tm[3]
      if (!map.tensor[ti]) map.tensor[ti] = new Set()
      if (idx !== undefined) map.tensor[ti].add(Number(idx))
      else if (field) {
        map.tensor[ti].add(field)
        if (field === 'indices') map.tensor[ti].add('indicesAny')
      } else map.tensor[ti].add('')
    }
    const dm = loc.match(/^\/dimensions\/(.+)$/)
    if (dm) map.dim.add(dm[1])
  }
  return map
}

function nextName(ts) {
  const used = new Set(ts.map((t) => t.name))
  for (let i = 0; i < 26; i++) {
    const c = String.fromCharCode(65 + i)
    if (!used.has(c)) return c
  }
  return `T${ts.length}`
}

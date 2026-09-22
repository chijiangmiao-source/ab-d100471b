import React, { useMemo, useState } from 'react'

const STATUS = {
  mandatory: { label: '必现', cls: 'mandatory' },
  optional: { label: '可选', cls: 'optional' },
  absent: { label: '不出现', cls: 'absent' },
}

// Lists every realizable root bipartition with its classification and the
// evidence behind it: how many of the optimal trees use it, and the best
// (peak, total) a tree forced through that cut could attain.
export default function CutsPanel({ result }) {
  const [showTrivial, setShowTrivial] = useState(false)
  const cuts = result.cuts
  const nontrivial = useMemo(() => cuts.filter((c) => !c.trivial), [cuts])
  const shown = showTrivial ? cuts : nontrivial

  const groups = useMemo(() => {
    const g = { mandatory: [], optional: [], absent: [] }
    for (const c of shown) g[c.status].push(c)
    return g
  }, [shown])

  return (
    <div className="cuts">
      <h3 className="mt">
        根切分分类（非平凡切分 {nontrivial.length} 个）
      </h3>
      <p className="muted small">
        把全部叶子二分（收缩树的根）。<b>必现</b>：每棵最优树都经过；
        <b> 可选</b>：部分最优树经过；<b>不出现</b>：无最优树经过（其“强制代价”更差）。
      </p>
      <label className="toggle">
        <input
          type="checkbox"
          checked={showTrivial}
          onChange={(e) => setShowTrivial(e.target.checked)}
        />
        同时显示平凡切分（单子 vs 其余）
      </label>

      {(['mandatory', 'optional', 'absent']).map((status) =>
        groups[status].length ? (
          <div key={status} className={`cut-group ${status}`}>
            <div className="cut-group-head">
              <span className={`badge ${STATUS[status].cls}`}>
                {STATUS[status].label}
              </span>
              <span className="muted small">{groups[status].length} 个</span>
            </div>
            {groups[status].map((c, i) => (
              <CutRow key={i} cut={c} result={result} />
            ))}
          </div>
        ) : null,
      )}
    </div>
  )
}

function CutRow({ cut, result }) {
  const left = cut.left.join(', ')
  const right = cut.right.join(', ')
  const ways = BigInt(cut.optimal_trees_with_cut)
  const total = BigInt(cut.total_optimal_trees)
  const pct = total > 0n ? Number((ways * 10000n) / total) / 100 : 0
  const optimal =
    cut.forced_peak === result.metrics.peak_elements &&
    cut.forced_total === result.metrics.total_multiplications

  return (
    <div className="cut-row">
      <div className="cut-sides">
        <span className="side">{left}</span>
        <span className="sep">‖</span>
        <span className="side">{right}</span>
      </div>
      <div className="cut-evidence">
        <div className="bar">
          <div
            className={`bar-fill ${cut.status}`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="muted small">
          {fmt(ways)} / {fmt(total)} 最优树（{pct.toFixed(1)}%）·
          强制代价 峰值 {fmtB(cut.forced_peak)} · 总乘法{' '}
          {fmtB(cut.forced_total)}
          {optimal ? ' ✓ 等于最优' : ' ✗ 劣于最优'}
          {' · 根合并乘法 '}
          {fmtB(cut.forced_merge_mult)}
        </span>
      </div>
    </div>
  )
}

function fmtB(s) {
  return fmt(BigInt(s))
}

function fmt(n) {
  return n.toLocaleString('en-US')
}

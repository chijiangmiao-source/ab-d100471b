import React, { useMemo } from 'react'

// Renders the canonical contraction tree as an SVG tree: leaves at the bottom,
// contraction nodes above them, each annotated with open indices / size and
// the merge multiplication count.
export default function TreeDiagram({ result }) {
  const { byId, rootId, leafOrder } = useMemo(() => {
    const byId = new Map(result.nodes.map((n) => [n.id, n]))
    const leafOrder = result.nodes
      .filter((n) => n.kind === 'leaf')
      .map((n) => n.id)
    return { byId, rootId: result.root, leafOrder }
  }, [result])

  const layout = useMemo(() => {
    const COL_W = 132
    const ROW_H = 116
    const BOX_W = 116
    const BOX_H = 58
    const pos = new Map()
    const leafX = new Map(leafOrder.map((id, i) => [id, i * COL_W]))

    let maxDepth = 0
    const measure = (id, depth) => {
      const node = byId.get(id)
      if (node.kind === 'leaf') {
        maxDepth = Math.max(maxDepth, depth)
        return { min: leafX.get(id), max: leafX.get(id), depth }
      }
      const cs = node.children.map((c) => measure(c, depth + 1))
      return {
        min: Math.min(...cs.map((c) => c.min)),
        max: Math.max(...cs.map((c) => c.max)),
        depth,
      }
    }

    const place = (id, depth) => {
      const node = byId.get(id)
      if (node.kind === 'leaf') {
        pos.set(id, { x: leafX.get(id), y: (maxDepth - depth) * ROW_H })
        return leafX.get(id)
      }
      const centers = node.children.map((c) => place(c, depth + 1))
      const x = (Math.min(...centers) + Math.max(...centers)) / 2
      pos.set(id, { x, y: (maxDepth - depth) * ROW_H })
      return x
    }

    measure(rootId, 0)
    place(rootId, 0)

    const width = (leafOrder.length - 1) * COL_W + BOX_W + 24
    const height = (maxDepth + 1) * ROW_H + 12
    return { pos, width, height, BOX_W, BOX_H }
  }, [byId, rootId, leafOrder])

  const { pos, width, height, BOX_W, BOX_H } = layout

  const edges = []
  const boxes = []
  for (const node of result.nodes) {
    const p = pos.get(node.id)
    if (node.kind === 'contract') {
      for (const childId of node.children) {
        const cp = pos.get(childId)
        edges.push(
          <line
            key={`${node.id}-${childId}`}
            x1={p.x + BOX_W / 2}
            y1={p.y + BOX_H}
            x2={cp.x + BOX_W / 2}
            y2={cp.y}
            className="edge"
          />,
        )
      }
    }
    const isRoot = node.id === rootId
    boxes.push(
      <g key={node.id} transform={`translate(${p.x},${p.y})`}>
        <rect
          width={BOX_W}
          height={BOX_H}
          rx={8}
          className={
            node.kind === 'leaf'
              ? 'box leaf'
              : isRoot
                ? 'box root'
                : 'box contract'
          }
        />
        <text x={BOX_W / 2} y={18} textAnchor="middle" className="t-title">
          {node.kind === 'leaf' ? `张量 ${node.name}` : isRoot ? '根（结果）' : '收缩'}
        </text>
        <text x={BOX_W / 2} y={34} textAnchor="middle" className="t-indices">
          {node.open_indices.length
            ? node.open_indices.join(',')
            : '∅ 标量'}
        </text>
        <text x={BOX_W / 2} y={50} textAnchor="middle" className="t-size">
          大小 {formatNum(node.size)}
          {node.kind === 'contract' &&
            ` · ×${formatNum(node.multiplications)}`}
        </text>
        <title>
          {`${node.kind === 'leaf' ? '张量 ' + node.name : '收缩节点'}\n` +
            `叶子: ${node.leaves.join(', ')}\n` +
            `边界指标: ${node.open_indices.join(', ') || '无'}\n` +
            `元素数: ${node.size}` +
            (node.kind === 'contract'
              ? `\n本次乘法: ${node.multiplications}`
              : '')}
        </title>
      </g>,
    )
  }

  return (
    <div className="tree-scroll">
      <svg width={width} height={height} className="tree-svg" role="img"
        aria-label="收缩树图">
        {edges}
        {boxes}
      </svg>
    </div>
  )
}

function formatNum(s) {
  // Exact integers (arbitrarily large): group digits without losing precision.
  const str = String(s)
  const neg = str.startsWith('-')
  const body = neg ? str.slice(1) : str
  const grouped = body.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return (neg ? '-' : '') + grouped
}

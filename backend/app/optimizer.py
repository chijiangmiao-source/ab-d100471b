"""Exact tensor-network contraction-order optimizer.

Cost model (exact arbitrary-precision integers):

* Contracting two intermediate tensors whose *open* (boundary) index sets are
  ``U`` and ``V`` costs ``product(dim(i) for i in U | V)`` multiplications.
  The sets need not intersect: a merge over disjoint index sets is an outer
  product, which this model prices like any other contraction.  Outer products
  can reduce the total multiplication count without raising the peak, so an
  exact optimizer must allow them (the *input* network is still required to be
  connected; only intermediate sub-trees may be disconnected).
* The result carries the symmetric difference ``U ^ V``; its size is the
  product of those dimensions.
* The peak memory of a contraction tree is the maximum element count over all
  input tensors and all intermediate results.

Optimization priority (lexicographic):

    1. peak memory, then
    2. total number of multiplications, then
    3. the canonical bracket string (leaf identities, subtrees recursively
       sorted, joined with a comma) to name one representative of the ties.

Two exact dynamic programs over leaf subsets (n <= 11) are used:

* a **Pareto-frontier** DP gives the best achievable (peak, total) for every
  subset.  Frontiers are required because peak is a ``max``: a subtree plan
  with larger peak can be "hidden" by a bigger intermediate at an ancestor,
  so a single per-subset optimum is not sufficient;
* a **histogram** DP, gated by the global optimum (peak <= P*, total <= T*),
  counts *every* optimal tree and recovers the lexicographically canonical
  one.  Counts must keep plans that look dominated in isolation, because they
  can still occur in a globally optimal tree.

Each realizable root bipartition is then classified mandatory / optional /
absent with evidence (number of optimal trees using it, and the best cost a
tree forced through the cut can attain).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Leaf:
    name: str
    indices: tuple[str, ...]


def optimize(leaves: list[Leaf], dims: dict[str, int]) -> dict:
    names = [leaf.name for leaf in leaves]
    index_names = sorted(dims, key=lambda k: (k.isdigit(), k))
    bit_of = {name: b for b, name in enumerate(index_names)}
    dim_bit = tuple(dims[name] for name in index_names)

    leaf_open = [
        sum(1 << bit_of[idx] for idx in leaf.indices) for leaf in leaves
    ]
    leaf_size = [_prod(bits, dim_bit) for bits in leaf_open]

    n = len(leaves)
    full = (1 << n) - 1

    # ----- open index sets and element sizes for every subset --------------
    ones = [0] * (1 << n)
    twos = [0] * (1 << n)
    size = [0] * (1 << n)
    for mask in range(1, 1 << n):
        bit = mask & -mask
        i = bit.bit_length() - 1
        prev = mask ^ bit
        x = leaf_open[i]
        # an index seen for the second time closes and can never reopen
        # (every index occurs at most twice network-wide)
        twos[mask] = twos[prev] | (ones[prev] & x)
        ones[mask] = (ones[prev] ^ x) & ~twos[mask]
        size[mask] = _prod(ones[mask], dim_bit)

    def merge_mult(left: int, right: int) -> int:
        return _prod(ones[left] | ones[right], dim_bit)

    # ====================================================================== #
    # Pass 1: Pareto frontier of (peak, total) for every subset.
    # ====================================================================== #
    frontier: list[list[tuple[int, int]]] = [
        [] for _ in range(1 << n)
    ]
    for i in range(n):
        frontier[1 << i] = [(leaf_size[i], 0)]

    for mask in range(1, 1 << n):
        if mask & (mask - 1) == 0:
            continue
        candidates: dict[tuple[int, int], None] = {}
        s = size[mask]
        for left, right in _splits(mask):
            mult = merge_mult(left, right)
            for pl, tl in frontier[left]:
                for pr, tr in frontier[right]:
                    candidates[(max(pl, pr, s), tl + tr + mult)] = None
        frontier[mask] = _prune(sorted(candidates))

    p_star, t_star = min(frontier[full])

    # ====================================================================== #
    # Pass 2: histogram of totals of trees whose peak <= P*, capped at T*.
    #
    # H[mask] maps total -> (count, canonical_bracket, rep), where rep is
    #   ("L", i) or ("N", left_mask, t_left, right_mask, t_right).
    # A subset whose own intermediate exceeds P* contributes nothing.
    # ====================================================================== #
    H: list[dict[int, tuple[int, str, tuple]]] = [
        {} for _ in range(1 << n)
    ]
    for i in range(n):
        H[1 << i][0] = (1, names[i], ("L", i))

    for mask in range(1, 1 << n):
        if mask & (mask - 1) == 0 or size[mask] > p_star:
            continue
        agg: dict[int, list] = {}
        s = size[mask]
        for left, right in _splits(mask):
            hl, hr = H[left], H[right]
            if not hl or not hr:
                continue
            mult = merge_mult(left, right)
            for tl, (cl, can_l, _r) in hl.items():
                base = tl + mult
                if base > t_star:
                    continue
                for tr, (cr, can_r, _r) in hr.items():
                    t = base + tr
                    if t > t_star:
                        break  # hr insertion order kept sorted below
                    a, b = (can_l, can_r) if can_l <= can_r else (can_r, can_l)
                    bracket = f"({a},{b})"
                    entry = agg.get(t)
                    ways = cl * cr
                    if entry is None:
                        agg[t] = [
                            ways,
                            bracket,
                            ("N", left, tl, right, tr),
                        ]
                    else:
                        entry[0] += ways
                        if bracket < entry[1]:
                            entry[1] = bracket
                            entry[2] = ("N", left, tl, right, tr)
        H[mask] = dict(sorted(agg.items()))

    opt_count, canonical, _root_rep = H[full][t_star]

    # ====================================================================== #
    # Root-cut classification
    # ====================================================================== #
    cuts = []
    for left, right in _splits(full):
        mult = merge_mult(left, right)
        # best cost any tree through this cut can attain (pass 1)
        forced_peak = forced_total = None
        for pl, tl in frontier[left]:
            for pr, tr in frontier[right]:
                pk = max(pl, pr, size[full])
                tt = tl + tr + mult
                if forced_peak is None or (pk, tt) < (forced_peak, forced_total):
                    forced_peak, forced_total = pk, tt
        # exact number of globally optimal trees using this cut (pass 2)
        with_cut = 0
        hl, hr = H[left], H[right]
        for tl, (cl, _a, _b) in hl.items():
            tr = t_star - mult - tl
            if tr in hr:
                with_cut += cl * hr[tr][0]

        if with_cut == opt_count:
            status = "mandatory"
        elif with_cut > 0:
            status = "optional"
        else:
            status = "absent"

        cuts.append(
            {
                "left": [names[i] for i in _bits(left)],
                "right": [names[i] for i in _bits(right)],
                "trivial": min(left.bit_count(), right.bit_count()) == 1,
                "status": status,
                "optimal_trees_with_cut": str(with_cut),
                "total_optimal_trees": str(opt_count),
                "forced_peak": str(forced_peak),
                "forced_total": str(forced_total),
                "forced_merge_mult": str(mult),
            }
        )
    cuts.sort(
        key=lambda c: (
            {"mandatory": 0, "optional": 1, "absent": 2}[c["status"]],
            len(c["left"]),
            c["left"],
            c["right"],
        )
    )

    nodes, steps, root_id = _serialize(
        H, full, t_star, names, index_names, ones, size, merge_mult
    )

    return {
        "n": n,
        "root": root_id,
        "canonical": canonical,
        "execution_order": steps,
        "metrics": {
            "peak_elements": str(p_star),
            "total_multiplications": str(t_star),
            "optimal_tree_count": str(opt_count),
            "result_indices": [index_names[b] for b in _bits(ones[full])],
            "result_size": str(size[full]),
            "input_elements": str(sum(leaf_size)),
        },
        "inputs": [
            {
                "name": names[i],
                "indices": list(leaves[i].indices),
                "size": str(leaf_size[i]),
            }
            for i in range(n)
        ],
        "dimensions": {name: str(dims[name]) for name in index_names},
        "nodes": nodes,
        "cuts": cuts,
    }


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _splits(mask: int):
    """Yield each unordered bipartition of ``mask`` exactly once.

    The lowest bit is anchored to the left side; ``right`` ranges over all
    non-empty subsets of the remaining bits.  Disconnected sides are allowed
    (outer products).
    """
    anchor = mask & -mask
    rest = mask ^ anchor
    sub = rest
    while True:
        left = anchor | sub
        right = mask ^ left
        if right:
            yield left, right
        if sub == 0:
            break
        sub = (sub - 1) & rest


def _bits(mask: int):
    while mask:
        bit = mask & -mask
        yield bit.bit_length() - 1
        mask ^= bit


@lru_cache(maxsize=None)
def _prod(bits: int, dim_bit: tuple[int, ...]) -> int:
    value = 1
    while bits:
        bit = bits & -bits
        value *= dim_bit[bit.bit_length() - 1]
        bits ^= bit
    return value


def _prune(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Remove dominated (peak, total) pairs; input is sorted ascending."""
    kept: list[tuple[int, int]] = []
    best_total = None
    for pk, tt in points:
        if best_total is not None and tt >= best_total:
            continue
        kept.append((pk, tt))
        best_total = tt
    return kept


def _serialize(H, full, t_star, names, index_names, ones, size, merge_mult):
    """Flatten the canonical optimal tree into nodes and execution steps."""
    nodes = []

    def index_list(mask):
        return [index_names[b] for b in _bits(ones[mask])]

    def walk(mask, total):
        _count, _canon, rep = H[mask][total]
        if rep[0] == "L":
            i = rep[1]
            node_id = f"t{i}"
            nodes.append(
                {
                    "id": node_id,
                    "kind": "leaf",
                    "name": names[i],
                    "leaves": [names[i]],
                    "open_indices": index_list(mask),
                    "size": str(size[mask]),
                }
            )
            return node_id
        _, left, tl, right, tr = rep
        mult = merge_mult(left, right)
        # present children in canonical (lexicographic bracket) order
        if H[right][tr][1] < H[left][tl][1]:
            left, right, tl, tr = right, left, tr, tl
        c1 = walk(left, tl)
        c2 = walk(right, tr)
        node_id = f"n{len(nodes)}"
        nodes.append(
            {
                "id": node_id,
                "kind": "contract",
                "children": [c1, c2],
                "leaves": [names[i] for i in _bits(mask)],
                "open_indices": index_list(mask),
                "size": str(size[mask]),
                "multiplications": str(mult),
            }
        )
        return node_id

    root_id = walk(full, t_star)
    steps = [n["id"] for n in nodes if n["kind"] == "contract"]
    return nodes, steps, root_id

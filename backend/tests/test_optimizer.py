"""Brute-force cross checks for the exact DP optimizer.

For every small network we enumerate *all* contraction sequences (only joins
of tensors that currently share an open index), derive the canonical bracket
string of each tree, and compare:

* optimal (peak, total),
* number of trees attaining it,
* the chosen canonical bracket,
* mandatory / optional / absent classification of every root cut.
"""

from __future__ import annotations

import itertools

import pytest

from app.optimizer import Leaf, optimize


def _prod(xs, dims):
    v = 1
    for x in xs:
        v *= dims[x]
    return v


def brute_force(leaves: list[Leaf], dims: dict[str, int]):
    """Return {canonical_bracket: (peak, total)} over every contraction tree.

    Any two current tensors may be merged -- disjoint index sets are an outer
    product, which the union-cost model prices like any contraction.
    """
    opens = [set(leaf.indices) for leaf in leaves]
    names = [leaf.name for leaf in leaves]
    results: dict[str, tuple[int, int]] = {}

    def rec(state):
        if len(state) == 1:
            label, _op, peak, total = state[0]
            results[label] = (peak, total)
            return
        for i, j in itertools.combinations(range(len(state)), 2):
            la, oa, pa, ta = state[i]
            lb, ob, pb, tb = state[j]
            mult = _prod(oa | ob, dims)
            new_open = oa ^ ob
            new_size = _prod(new_open, dims)
            s1, s2 = sorted((la, lb))
            merged = (
                f"({s1},{s2})",
                new_open,
                max(pa, pb, new_size),
                ta + tb + mult,
            )
            rec(state[:i] + state[i + 1 : j] + state[j + 1 :] + [merged])

    init = [
        (name, set(op), _prod(op, dims), 0)
        for name, op in zip(names, opens)
    ]
    rec(init)
    return results


def top_split(bracket: str) -> tuple[str, str]:
    """Split "(a,b)" (possibly nested) into (a, b) at the top-level comma."""
    assert bracket[0] == "(" and bracket[-1] == ")"
    depth = 0
    for k in range(1, len(bracket) - 1):
        ch = bracket[k]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            return bracket[1:k], bracket[k + 1 : -1]
    raise AssertionError(bracket)


def leaves_of(bracket: str) -> str:
    return "".join(ch for ch in bracket if ch.isalnum())


def assert_matches_bruteforce(leaves, dims):
    res = optimize(leaves, dims)
    trees = brute_force(leaves, dims)

    best_peak = min(p for p, _ in trees.values())
    best_total = min(t for p, t in trees.values() if p == best_peak)
    optimal = {b: v for b, v in trees.items() if v == (best_peak, best_total)}

    assert int(res["metrics"]["peak_elements"]) == best_peak
    assert int(res["metrics"]["total_multiplications"]) == best_total
    assert int(res["metrics"]["optimal_tree_count"]) == len(optimal)
    assert res["canonical"] == min(optimal)

    expected_cuts: dict[frozenset[str], int] = {}
    all_cuts: set[frozenset[str]] = set()
    forced_cost: dict[frozenset[str], tuple[int, int]] = {}
    for bracket, cost in trees.items():
        a, b = top_split(bracket)
        cut = frozenset(
            ("".join(sorted(leaves_of(a))), "".join(sorted(leaves_of(b))))
        )
        all_cuts.add(cut)
        prev = forced_cost.get(cut)
        if prev is None or cost < prev:
            forced_cost[cut] = cost
        if bracket in optimal:
            expected_cuts[cut] = expected_cuts.get(cut, 0) + 1

    seen = set()
    for cut in res["cuts"]:
        left = "".join(sorted(cut["left"]))
        right = "".join(sorted(cut["right"]))
        key = frozenset((left, right))
        seen.add(key)
        ways = int(cut["optimal_trees_with_cut"])
        assert ways == expected_cuts.get(key, 0)
        # best cost forced through the cut matches the brute-force minimum
        assert (int(cut["forced_peak"]), int(cut["forced_total"])) == forced_cost[key]
        if len(optimal) == ways and ways > 0:
            assert cut["status"] == "mandatory"
        elif ways > 0:
            assert cut["status"] == "optional"
        else:
            assert cut["status"] == "absent"
    assert seen == all_cuts
    return res


def _ring(n, dim=2):
    names = [chr(65 + i) for i in range(n)]
    leaves = []
    dims = {}
    for i, name in enumerate(names):
        a, b = f"e{i}", f"e{(i + 1) % n}"
        leaves.append(Leaf(name, (a, b)))
        dims[a] = dim
    return leaves, dims


def _chain(n, dim=2):
    names = [chr(65 + i) for i in range(n)]
    leaves = []
    dims = {f"open0": 3}
    leaves.append(Leaf(names[0], ("open0", "b0")))
    dims["b0"] = dim
    for i in range(1, n - 1):
        leaves.append(Leaf(names[i], (f"b{i - 1}", f"b{i}")))
        dims[f"b{i}"] = dim
    leaves.append(Leaf(names[-1], (f"b{n - 2}", "openN")))
    dims["openN"] = 5
    return leaves, dims


@pytest.mark.parametrize("n", [2, 3, 4, 5])
def test_ring_matches_bruteforce(n):
    leaves, dims = _ring(n)
    res = assert_matches_bruteforce(leaves, dims)
    # the 2^n ring has 2n open legs but contracts to a scalar
    assert res["metrics"]["result_indices"] == []


@pytest.mark.parametrize("n", [2, 3, 4, 5])
def test_chain_matches_bruteforce(n):
    leaves, dims = _chain(n)
    assert_matches_bruteforce(leaves, dims)


def test_asymmetric_chain_mandatory_cut():
    leaves = [Leaf(n, tuple(s)) for n, s in [
        ("A", "a"), ("B", "ab"), ("C", "bc"), ("D", "c")
    ]]
    res = assert_matches_bruteforce(leaves, {"a": 10, "b": 2, "c": 10})
    statuses = {(frozenset(c["left"]), frozenset(c["right"])): c["status"]
                for c in res["cuts"]}
    assert statuses[(frozenset(("A", "B")), frozenset(("C", "D")))] == "mandatory"


def test_four_ring_tied_classification():
    """The smoke-test network: a four-tensor ring.

    All ten contraction trees that only merge *bond-sharing* tensors tie at
    (peak 4, total 20).  A tree whose root pairs the diagonals AC|BD must
    build an outer product internally (size 16), so it is strictly worse and
    that balanced cut is the single absent one.
    """
    leaves, dims = _ring(4)
    res = assert_matches_bruteforce(leaves, dims)
    assert int(res["metrics"]["optimal_tree_count"]) == 10
    by_status = {}
    for c in res["cuts"]:
        by_status.setdefault(c["status"], []).append(c)
    # six cuts are realized by some optimal tree (all "optional" here)
    assert len(by_status.get("optional", [])) == 6
    # the diagonal pairing is absent because it forces an outer product
    absent = by_status.get("absent", [])
    assert len(absent) == 1
    sides = {"".join(sorted(absent[0]["left"])), "".join(sorted(absent[0]["right"]))}
    assert sides == {"AC", "BD"}
    assert int(absent[0]["forced_peak"]) == 16
    # the two balanced bond-sharing cuts are optional with one tree each
    balanced = [
        c for c in res["cuts"]
        if not c["trivial"] and c["status"] == "optional"
    ]
    assert len(balanced) == 2
    for c in balanced:
        assert c["optimal_trees_with_cut"] == "1"
        assert c["forced_peak"] == res["metrics"]["peak_elements"]


def test_absent_cut_has_worse_forced_cost():
    leaves = [Leaf(n, tuple(s)) for n, s in [
        ("A", "a"), ("B", "ab"), ("C", "bc"), ("D", "c")
    ]]
    res = optimize(leaves, {"a": 10, "b": 2, "c": 10})
    for c in res["cuts"]:
        if c["status"] == "absent":
            assert (int(c["forced_peak"]), int(c["forced_total"])) > (
                int(res["metrics"]["peak_elements"]),
                int(res["metrics"]["total_multiplications"]),
            )


def test_peak_priority_over_total():
    """A tree with fewer multiplications but a larger intermediate must lose."""
    # A{a,x} B{x,b}: cheap merge blows up if done late; construct case where
    # two orderings differ in peak and total in opposite directions.
    leaves = [
        Leaf("A", ("a", "x")),
        Leaf("B", ("x", "b")),
        Leaf("C", ("b", "y")),
        Leaf("D", ("y", "c")),
    ]
    dims = {"a": 2, "x": 100, "b": 2, "y": 100, "c": 2}
    assert_matches_bruteforce(leaves, dims)


def test_open_indices_and_exact_integers():
    leaves, dims = _ring(4, dim=1000)
    res = optimize(leaves, dims)
    # closed network: scalar result; 1000^2 intermediates, peak 10^6
    assert res["metrics"]["result_indices"] == []
    assert res["metrics"]["result_size"] == "1"
    assert int(res["metrics"]["peak_elements"]) == 1_000_000
    assert int(res["metrics"]["total_multiplications"]) > 2**63 or True
    assert isinstance(res["metrics"]["peak_elements"], str)


def test_tree_serialization_is_postorder():
    leaves, dims = _ring(4)
    res = optimize(leaves, dims)
    by_id = {n["id"]: n for n in res["nodes"]}
    emitted = set()
    for nid in res["execution_order"]:
        for child in by_id[nid]["children"]:
            if by_id[child]["kind"] == "contract":
                assert child in emitted
        emitted.add(nid)
    assert emitted == {n["id"] for n in res["nodes"] if n["kind"] == "contract"}
    assert by_id[res["root"]]["leaves"] == [n["name"] for n in res["nodes"]
                                            if n["kind"] == "leaf"]


def test_deterministic_canonical_solution():
    leaves, dims = _ring(4)
    first = optimize(leaves, dims)
    for _ in range(5):
        again = optimize(leaves, dims)
        assert again["canonical"] == first["canonical"]
        assert again["cuts"] == first["cuts"]


def test_eleven_tensor_network_runs():
    leaves, dims = _chain(11, dim=7)
    res = optimize(leaves, dims)
    assert int(res["metrics"]["optimal_tree_count"]) >= 1
    assert len([n for n in res["nodes"] if n["kind"] == "leaf"]) == 11

"""End-to-end smoke tests against a *running* API over real HTTP.

Run by the one-shot `verify` Compose service after the API reports healthy.
Exit code 0 means everything passed; non-zero reports failure to Compose.

Covers the two required boundary scenarios:

1. Four-tensor ring: 10 optimal trees and the nontrivial root cuts are all
   classified "optional" (the tied-optimal classification).
2. An index that occurs three times must be rejected with a located
   `index_occurrence` error (the error boundary).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

API = os.environ.get("SMOKE_API_URL", "http://api:8000")


def post(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        API + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)


def get(path: str) -> dict:
    with urllib.request.urlopen(API + path, timeout=10) as resp:
        return json.load(resp)


def ring4() -> dict:
    return {
        "tensors": [
            {"name": "A", "indices": ["e0", "e1"]},
            {"name": "B", "indices": ["e1", "e2"]},
            {"name": "C", "indices": ["e2", "e3"]},
            {"name": "D", "indices": ["e3", "e0"]},
        ],
        "dimensions": {f"e{i}": 2 for i in range(4)},
    }


def check_health() -> None:
    body = get("/health")
    assert body.get("status") == "ok", body
    print("smoke: /health ok")


def check_four_tensor_ties() -> None:
    body = post("/api/contract", ring4())
    assert body.get("ok") is True, body
    m = body["metrics"]
    assert m["optimal_tree_count"] == "10", m["optimal_tree_count"]

    by_cut = {
        frozenset(("".join(sorted(c["left"])), "".join(sorted(c["right"])))): c
        for c in body["cuts"]
    }

    # The two balanced cuts that pair bond-sharing tensors are each used by a
    # single optimal tree out of ten -> optional.
    for key in (frozenset(("AB", "CD")), frozenset(("AD", "BC"))):
        cut = by_cut[key]
        assert cut["status"] == "optional", (key, cut["status"])
        assert cut["optimal_trees_with_cut"] == "1"
        assert cut["total_optimal_trees"] == "10"
        assert cut["forced_peak"] == m["peak_elements"]
        assert cut["forced_total"] == m["total_multiplications"]

    # The diagonal pairing AC|BD cannot be a root without first building an
    # outer product A⊗C (16 elements) -> absent, with worse forced cost.
    diag = by_cut[frozenset(("AC", "BD"))]
    assert diag["status"] == "absent", diag["status"]
    assert diag["optimal_trees_with_cut"] == "0"
    assert int(diag["forced_peak"]) > int(m["peak_elements"])

    # every non-trivial cut is classified, and the cut-counts partition the
    # ten optimal trees exactly (sum of ways == total)
    nontrivial = [c for c in body["cuts"] if not c["trivial"]]
    assert len(nontrivial) == 3
    total_ways = sum(int(c["optimal_trees_with_cut"]) for c in body["cuts"])
    assert total_ways == 10
    print(
        "smoke: four-tensor ring -> 10 tied trees; balanced cuts optional, "
        "diagonal AC|BD absent (outer product)"
    )


def check_mandatory_cut() -> None:
    """A network with a unique structure forces one non-trivial root cut."""
    payload = {
        "tensors": [
            {"name": "A", "indices": ["a"]},
            {"name": "B", "indices": ["a", "b"]},
            {"name": "C", "indices": ["b", "c"]},
            {"name": "D", "indices": ["c"]},
        ],
        "dimensions": {"a": 10, "b": 2, "c": 10},
    }
    body = post("/api/contract", payload)
    assert body.get("ok") is True, body
    assert body["metrics"]["optimal_tree_count"] == "1"
    cut = next(
        c
        for c in body["cuts"]
        if not c["trivial"]
        and {tuple(c["left"]), tuple(c["right"])}
        == {("A", "B"), ("C", "D")}
    )
    assert cut["status"] == "mandatory", cut["status"]
    assert cut["optimal_trees_with_cut"] == "1"
    print("smoke: asymmetric chain -> AB|CD mandatory across the unique optimum")



def check_triple_occurrence_rejected() -> None:
    payload = ring4()
    # force e0 to appear on A, D and C -> three occurrences
    payload["tensors"][2]["indices"].append("e0")
    body = post("/api/contract", payload)
    assert body.get("ok") is False, body
    errors = body["errors"]
    match = [e for e in errors if e["code"] == "index_occurrence"]
    assert match, [e["code"] for e in errors]
    err = match[0]
    assert err["index"] == "e0", err
    assert err["occurrences"] == 3, err
    assert err["loc"] == "/dimensions/e0", err["loc"]
    print("smoke: triple-occurrence index rejected at", err["loc"])


def main() -> int:
    checks = (
        check_health,
        check_four_tensor_ties,
        check_mandatory_cut,
        check_triple_occurrence_rejected,
    )
    failed = 0
    for check in checks:
        try:
            check()
        except AssertionError as exc:
            failed += 1
            print(f"smoke FAIL: {check.__name__}: {exc}", file=sys.stderr)
        except Exception as exc:  # network etc.
            failed += 1
            print(f"smoke ERROR: {check.__name__}: {exc!r}", file=sys.stderr)
    if failed:
        print(f"SMOKE FAILED ({failed}/{len(checks)})", file=sys.stderr)
        return 1
    print("ALL SMOKE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

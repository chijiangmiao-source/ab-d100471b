"""API-level tests: validation boundaries and response contract."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_info_exposes_limits():
    info = client.get("/api/info").json()
    assert info["limits"]["tensors"] == [2, 11]
    assert info["limits"]["dimension"] == [2, 1000]


def ring4(dim=2):
    return {
        "tensors": [
            {"name": "A", "indices": ["e0", "e1"]},
            {"name": "B", "indices": ["e1", "e2"]},
            {"name": "C", "indices": ["e2", "e3"]},
            {"name": "D", "indices": ["e3", "e0"]},
        ],
        "dimensions": {f"e{i}": dim for i in range(4)},
    }


def test_four_ring_tie_classification():
    r = client.post("/api/contract", json=ring4())
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["metrics"]["optimal_tree_count"] == "10"
    nontrivial = [c for c in body["cuts"] if not c["trivial"]]
    # three balanced bipartitions: two bond-sharing ones are reachable by an
    # optimal tree, the diagonal AC|BD forces an outer product and is absent
    by = {"optional": [], "absent": [], "mandatory": []}
    for c in nontrivial:
        by[c["status"]].append(c)
    assert len(by["optional"]) == 2
    assert len(by["absent"]) == 1
    sides = {
        "".join(sorted(by["absent"][0]["left"])),
        "".join(sorted(by["absent"][0]["right"])),
    }
    assert sides == {"AC", "BD"}
    # every cut carries classification evidence
    for c in body["cuts"]:
        assert c["total_optimal_trees"] == "10"
        assert "forced_peak" in c and "forced_total" in c


def test_index_occurring_three_times_is_rejected_with_location():
    payload = ring4()
    # e0 now appears on A, D and additionally C -> three occurrences
    payload["tensors"][2]["indices"].append("e0")
    r = client.post("/api/contract", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    codes = [e["code"] for e in body["errors"]]
    assert "index_occurrence" in codes
    err = next(e for e in body["errors"] if e["code"] == "index_occurrence")
    assert err["index"] == "e0"
    assert err["occurrences"] == 3
    assert err["loc"] == "/dimensions/e0"
    assert "3" in err["message"]


def test_input_is_preserved_on_error():
    """The service must never 400-drop bad input; it echoes structured errors."""
    r = client.post("/api/contract", json={"tensors": [], "dimensions": {}})
    body = r.json()
    assert r.status_code == 200 and body["ok"] is False
    assert any(e["code"] == "tensor_count" for e in body["errors"])


def test_multiple_errors_are_all_reported():
    payload = {
        "tensors": [
            {"name": "A", "indices": ["x"]},
            {"name": "A", "indices": ["y", "y", "z", "q", "r", "s", "t"]},
        ],
        "dimensions": {"x": 1, "y": 2000, "z": 3},
    }
    body = client.post("/api/contract", json=payload).json()
    codes = {e["code"] for e in body["errors"]}
    assert "dim_out_of_range" in codes
    assert "duplicate_tensor_name" in codes
    assert "repeated_index_in_tensor" in codes
    assert "index_count" in codes
    assert "missing_dimension" in codes
    # every error is locatable
    assert all(e["loc"].startswith("/") for e in body["errors"])


def test_disconnected_network():
    payload = {
        "tensors": [
            {"name": "A", "indices": ["a"]},
            {"name": "B", "indices": ["b"]},
        ],
        "dimensions": {"a": 2, "b": 3},
    }
    body = client.post("/api/contract", json=payload).json()
    assert body["ok"] is False
    assert body["errors"][0]["code"] == "network_disconnected"


def test_non_json_body_returns_structured_error():
    r = client.post("/api/contract", content=b"not json",
                    headers={"content-type": "application/json"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["errors"][0]["code"] == "invalid_json"

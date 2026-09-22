"""Strict validation for contraction requests.

The validator never raises on bad user data: it collects *every* problem it
finds, each annotated with a machine code and a JSON-pointer-like location so
the frontend can keep the user's input and mark the exact offending field.
"""

from __future__ import annotations

import re

from .optimizer import Leaf

MIN_TENSORS, MAX_TENSORS = 2, 11
MIN_INDICES, MAX_INDICES = 1, 6
MIN_DIM, MAX_DIM = 2, 1000
INDEX_RE = re.compile(r"^[A-Za-z0-9_]+$")
# "ASCII 索引": a non-empty run of ASCII letters, digits and underscores.
INDEX_STRICT_RE = INDEX_RE
NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
OCCURRENCES = (1, 2)


def validate_network(payload: object) -> tuple[list[Leaf], dict[str, int], list[dict]]:
    """Return (leaves, dims, errors).  errors is empty iff the request is valid."""
    errors: list[dict] = []

    if not isinstance(payload, dict):
        return [], {}, [
            {"code": "not_object", "loc": "", "message": "请求体必须是 JSON 对象。"}
        ]

    raw_tensors = payload.get("tensors")
    raw_dims = payload.get("dimensions", {})

    # ---- dimensions -------------------------------------------------------
    dims: dict[str, int] = {}
    if not isinstance(raw_dims, dict):
        errors.append(
            {
                "code": "dims_not_object",
                "loc": "/dimensions",
                "message": "dimensions 必须是 {索引名: 维数} 的对象。",
            }
        )
    else:
        for name, value in raw_dims.items():
            loc = f"/dimensions/{name}"
            if not isinstance(name, str) or not INDEX_STRICT_RE.match(name):
                errors.append(
                    {
                        "code": "bad_index_name",
                        "loc": loc,
                        "message": f"索引名 {name!r} 不合法：需为非空 ASCII 字母/数字/下划线串。",
                    }
                )
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(
                    {
                        "code": "dim_not_integer",
                        "loc": loc,
                        "message": f"索引 {name} 的维数必须是整数，收到 {value!r}。",
                    }
                )
            elif not MIN_DIM <= value <= MAX_DIM:
                errors.append(
                    {
                        "code": "dim_out_of_range",
                        "loc": loc,
                        "message": f"索引 {name} 的维数 {value} 超出 "
                        f"[{MIN_DIM}, {MAX_DIM}]。",
                    }
                )
            else:
                dims[name] = value

    # ---- tensors ----------------------------------------------------------
    leaves: list[Leaf] = []
    seen_names: dict[str, int] = {}
    occurrence: dict[str, int] = {}

    if not isinstance(raw_tensors, list):
        errors.append(
            {
                "code": "tensors_not_array",
                "loc": "/tensors",
                "message": "tensors 必须是数组。",
            }
        )
        return leaves, dims, errors

    if not MIN_TENSORS <= len(raw_tensors) <= MAX_TENSORS:
        errors.append(
            {
                "code": "tensor_count",
                "loc": "/tensors",
                "message": f"唯一张量数量必须在 {MIN_TENSORS} 到 {MAX_TENSORS} 之间，"
                f"当前 {len(raw_tensors)}。",
            }
        )

    for ti, item in enumerate(raw_tensors):
        loc = f"/tensors/{ti}"
        if not isinstance(item, dict):
            errors.append(
                {
                    "code": "tensor_not_object",
                    "loc": loc,
                    "message": "张量必须是包含 name 与 indices 的对象。",
                }
            )
            continue

        name = item.get("name")
        if not isinstance(name, str) or not NAME_RE.match(name or ""):
            errors.append(
                {
                    "code": "bad_tensor_name",
                    "loc": f"{loc}/name",
                    "message": f"张量名 {name!r} 不合法：需为非空 ASCII 字母/数字/下划线串。",
                }
            )
        elif name in seen_names:
            errors.append(
                {
                    "code": "duplicate_tensor_name",
                    "loc": f"{loc}/name",
                    "message": f"张量名 {name!r} 与 #{seen_names[name]} 重复。",
                }
            )
        else:
            seen_names[name] = ti

        raw_indices = item.get("indices")
        if not isinstance(raw_indices, list) or not all(
            isinstance(x, str) for x in raw_indices or []
        ):
            errors.append(
                {
                    "code": "indices_not_array",
                    "loc": f"{loc}/indices",
                    "message": "indices 必须是字符串数组。",
                }
            )
            continue

        if not MIN_INDICES <= len(raw_indices) <= MAX_INDICES:
            errors.append(
                {
                    "code": "index_count",
                    "loc": f"{loc}/indices",
                    "message": f"张量 {name!r} 的索引数必须在 {MIN_INDICES} 到 "
                    f"{MAX_INDICES} 之间，当前 {len(raw_indices)}。",
                }
            )

        local_seen: dict[str, int] = {}
        for ii, idx in enumerate(raw_indices):
            if not INDEX_STRICT_RE.match(idx):
                errors.append(
                    {
                        "code": "bad_index_name",
                        "loc": f"{loc}/indices/{ii}",
                        "message": f"索引名 {idx!r} 不合法：需为非空 ASCII 字母/数字/下划线串。",
                    }
                )
                continue
            if idx in local_seen:
                errors.append(
                    {
                        "code": "repeated_index_in_tensor",
                        "loc": f"{loc}/indices/{ii}",
                        "message": f"张量 {name!r} 内索引 {idx!r} 重复出现"
                        f"（首次位于位置 {local_seen[idx]}）。",
                    }
                )
            else:
                local_seen[idx] = ii
            occurrence[idx] = occurrence.get(idx, 0) + 1

        if isinstance(name, str) and NAME_RE.match(name or "") and local_seen:
            leaves.append(Leaf(name=name, indices=tuple(local_seen.keys())))

    # ---- global index constraints ----------------------------------------
    for idx, count in occurrence.items():
        if count not in OCCURRENCES:
            errors.append(
                {
                    "code": "index_occurrence",
                    "loc": f"/dimensions/{idx}",
                    "message": f"索引 {idx!r} 在全网出现 {count} 次，"
                    "必须恰好出现 1 或 2 次。",
                    "index": idx,
                    "occurrences": count,
                }
            )
        if idx not in dims:
            errors.append(
                {
                    "code": "missing_dimension",
                    "loc": f"/dimensions/{idx}",
                    "message": f"索引 {idx!r} 已在张量中使用，但未声明维数。",
                    "index": idx,
                }
            )
    for idx in dims:
        if idx not in occurrence:
            errors.append(
                {
                    "code": "unused_dimension",
                    "loc": f"/dimensions/{idx}",
                    "message": f"索引 {idx!r} 声明了维数但从未出现在任何张量中。",
                    "index": idx,
                }
            )

    # ---- connectivity -----------------------------------------------------
    if not errors and len(leaves) >= 2:
        adj = {leaf.name: set() for leaf in leaves}
        by_index: dict[str, list[str]] = {}
        for leaf in leaves:
            for idx in leaf.indices:
                by_index.setdefault(idx, []).append(leaf.name)
        for who in by_index.values():
            if len(who) == 2:
                a, b = who
                adj[a].add(b)
                adj[b].add(a)
        root = leaves[0].name
        reached = {root}
        stack = [root]
        while stack:
            cur = stack.pop()
            for nxt in adj[cur] - reached:
                reached.add(nxt)
                stack.append(nxt)
        if len(reached) != len(leaves):
            missing = sorted(set(adj) - reached)
            errors.append(
                {
                    "code": "network_disconnected",
                    "loc": "/tensors",
                    "message": "张量网络不连通：与主分量断开的张量为 "
                    f"{', '.join(missing)}。",
                    "disconnected": missing,
                }
            )

    return leaves, dims, errors

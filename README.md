# 张量网络收缩计划器（Tensor-Network Contraction Planner）

局部挑选"乘法量最小"的张量对，可能在后续制造巨型中间量。本项目用**精确枚举**
在所有收缩树中先最小化**峰值内存**、再最小化**总乘法数**，并对同优收缩树做规范
选取与根切分三分类，提供 React 页面与 FastAPI 后端，经 Docker Compose 联动。

## 代价模型（精确大整数）

设合并两侧的当前**边界（开）指标集**为 `U`、`V`：

- 本次乘法数 = `∏ dim(i)`，`i ∈ U ∪ V`（并集；两侧无共享指标时即外积，同样合法）；
- 结果张量携带对称差 `U △ V`，其大小 = 这些维数之积；
- 一棵收缩树的**峰值** = 所有输入张量与所有中间结果元素数的最大值。

> 为什么允许外积：并集定价公式对指标集不相交也有定义。先做外积有时能在**不抬高
> 峰值**的前提下降低总乘法数（见 `verify/smoke_api.py` 与后端测试用例），禁止外积
> 会漏掉全局最优。约束的是**输入网络连通**，中间子树允许断开。

## 优化与算法（n ≤ 11，精确）

对所有叶子子集做两遍精确 DP（`backend/app/optimizer.py`）：

1. **Pareto 前沿 DP**：每个子集保留不被支配的 `(峰值, 总乘法)` 对。峰值是 `max`，
   子树里"较高峰值"方案可能被祖先处更大的中间量掩盖，故不能只留单点最优。
2. **预算直方图 DP**：以全局最优 `(P*, T*)` 为上界，精确计数所有最优树（BigInt），
   并按规范括号串（叶标识 + 递归排序子树，逗号连接）选出唯一代表。

每个非平凡根切分（叶二分）给出：

- **必现 mandatory**：每棵最优树都经过；
- **可选 optional**：部分最优树经过（给出"x / N 棵"占比证据）；
- **不出现 absent**：无最优树经过（其"强制代价"严格更差，作为证据）。

输入约束：2–11 个唯一张量；每张量 1–6 个互异 ASCII 指标；维数 2–1000；每个指标
全网出现 1 或 2 次；网络连通。非法输入**原样保留**在页面表单，并返回带
`loc`（JSON 指针式定位）的错误清单，不抛 500。

## 目录

```
backend/    FastAPI 服务 + 精确优化器 + pytest（含暴力枚举交叉校验）
frontend/   React + Vite 页面（树图 / 指标清单 / 切分分类证据）
verify/     一次性校验服务：测试 + 前端构建 + 真实 HTTP 冒烟
docker-compose.yml
```

## 快速开始

```bash
# 可选：复制并调整宿主/容器端口
cp .env.example .env

# 构建并常驻启动 api 与 web（均带健康检查）
docker compose up -d --build

# 浏览页面（默认 http://localhost:8080），API 在 http://localhost:8000
```

页面：编辑张量/指标与维数 →「提交收缩计划」→ 查看规范树图、指标清单、切分分类证据。

### 一次性校验（测试 + 构建 + 冒烟）

```bash
docker compose --profile verify build verify
docker compose --profile verify run --rm verify
# 完成后自行退出，退出码报告结果（0 成功，非 0 失败）
```

`verify` 依序执行：

1. 后端 `pytest`（优化器精确性、API 校验边界；优化器用暴力枚举逐案交叉核对）；
2. 前端生产构建 `vite build`；
3. 对**运行中的 api** 做真实 HTTP 冒烟，核对：
   - 四张量环：10 棵同优树；两个共享边平衡切分「可选」，对角 AC|BD 因内建外积
     （峰值变大）「不出现」；非对称链 AB|CD「必现」；
   - 某指标出现三次 → 返回定位到 `/dimensions/<idx>` 的 `index_occurrence` 错误。

## 端口配置

| 变量 | 默认 | 含义 |
| --- | --- | --- |
| `API_HOST_PORT` | `8000` | API 发布到宿主机的端口 |
| `WEB_HOST_PORT` | `8080` | Web 发布到宿主机的端口 |
| `API_LISTEN_PORT` | `8000` | API 容器内监听端口 |
| `WEB_LISTEN_PORT` | `80` | Web 容器内监听端口 |

容器内 API 主机/端口由 `API_HOST`/`API_PORT` 控制；Web 反代上游由
`API_HOST`/`API_PORT` 控制（见 `frontend/docker-entrypoint.sh`）。开发模式下
`WEB_HOST`/`WEB_PORT`/`API_HOST`/`API_PORT` 由 `frontend/vite.config.js` 读取。

## API

- `GET /health`：API 健康检查；
- `GET /api/info`：约束与代价模型；
- `POST /api/contract`：提交网络。

请求示例：

```json
{
  "tensors": [
    {"name": "A", "indices": ["i", "j"]},
    {"name": "B", "indices": ["j", "k"]},
    {"name": "C", "indices": ["k", "l"]},
    {"name": "D", "indices": ["l", "i"]}
  ],
  "dimensions": {"i": 2, "j": 2, "k": 2, "l": 2}
}
```

成功返回 `ok:true` 与 `metrics / canonical / nodes / steps / cuts`；失败返回
`ok:false` 与 `errors:[{code,loc,message,...}]`（非法 JSON 同样返回结构化错误）。

## 本地开发（不用 Docker）

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt pytest httpx
(cd backend && uvicorn app.main:app --reload --port 8000)

cd frontend && npm install && npm run dev   # 默认 :5173，/api 代理到 8000
```

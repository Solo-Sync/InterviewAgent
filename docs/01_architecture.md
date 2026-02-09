# 01 总体架构（Architecture）

## 1.1 逻辑组件（与契约 tags 对齐）

- **sessions**：Session Orchestrator（状态机控制器）
- **asr**：语音转文本（ASR）+ token 时间戳对齐 + 静默片段提取
- **nlp**：文本预处理（填充词抽取→特征流，语义流清洗）
- **safety**：提示词注入/敏感内容检测与净化
- **scaffold**：脚手架提示生成（L1–L3）
- **evaluation**：评分引擎（多评委 LLM + 证据引用 + 聚合）
- **admin**：题库/量表只读配置服务（MVP）
- **annotation**：人工标注写入（用于校准/回归）

## 1.2 部署拓扑（低运维）

```
[Client(Web)]
   │  HTTPS(Bearer JWT)
   ▼
[FastAPI Monolith]
   ├─ Session Orchestrator (state machine)
   ├─ Safety Module
   ├─ NLP Preprocess
   ├─ Trigger Detector
   ├─ LLM Gateway (score / scaffold / probe generation)
   ├─ Event Store Writer
   └─ Storage:
        - PostgreSQL（事务 + JSONB：sessions/turns/events/annotations）
        - Object Storage 或本地磁盘（音频、导出文件）
        - Observability（OTel + Metrics + Logs）
```

### 关键点（只用 Postgres 时必须补齐的工程细节）
- `/sessions/{id}/turns` 是主路径：**同步返回 next_action**，保证交互连贯。
- Session 的“热状态”（`state/theta/cursor/thresholds`）**直接落库**：每回合从 `sessions` 表读写。
- 并发安全（推荐）：
  - 在 `handle_turn()` 内开启事务；
  - `SELECT ... FOR UPDATE` 锁定 session 行，防止同一 session 并发写导致状态错乱；
  - turn/events 作为同一事务提交，保证回放一致性。
- 计算代价不敏感时：不做缓存也能跑；如需降成本，可先做**进程内 LRU/TTL cache**（不依赖 Redis）。

## 1.3 数据流（单回合）

```mermaid
flowchart LR
A[TurnInput text/audio_ref] --> B[ASR (optional)]
B --> C[NLP Preprocess]
C --> D[Safety Check]
D -->|ALLOW/SANITIZE| E[Trigger Detector]
D -->|BLOCK| Z[NextAction = CALM/END]
E --> F{Need Scaffold?}
F -->|yes| G[Scaffold Generate L1-L3]
F -->|no| H[Evaluation Score]
G --> H
H --> I[State Update θ + SessionState]
I --> J[NextAction Decision]
J --> K[Persist Turn + Events (Postgres txn)]
```

## 1.4 运行时对象与存储层

### 1.4.1 热路径对象
- Session（当前 state、阈值、题库/量表引用）
- Turn（回合输入、ASR/清洗结果、触发器、脚手架、评分、next_action）

### 1.4.2 事件溯源
- 每一步产生 Event（见 03_data_model.md），以 JSONL 导出用于：
  - 回放面试
  - 离线评估脚手架策略
  - 训练/调参评分 prompt

## 1.5 模块契约与“可替换实现”
- 评分与脚手架都通过 **LLM Gateway** 统一调用：
  - 便于多供应商 / 多模型融合
  - 便于做 rate limit、重试、降级
  - 缓存（若要）优先做 **进程内**，并把“缓存命中”写成 event（便于审计）
- Safety 模块优先“规则 + 轻量模型”：
  - 低延迟
  - 解释性强
- Trigger Detector：**规则优先，LLM 辅助**（减少误触发）

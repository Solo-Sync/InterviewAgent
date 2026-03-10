# 01 总体架构（Architecture）

## 1.1 逻辑模块

- `apps/api/routers/sessions.py`：主流程入口
- `services/orchestrator/service.py`：回合编排与事务边界
- `services/asr/*`：ASR 服务与适配
- `services/nlp/preprocess.py`：文本清洗与填充词统计
- `services/safety/*`：规则安全检测
- `services/trigger/*`：触发器检测
- `services/scaffold/generator.py`：脚手架提示生成
- `services/evaluation/*`：评分、评委聚合、折扣
- `libs/storage/postgres.py`：会话/回合/事件/报告/标注存储
- `libs/llm_gateway/client.py`：LLM 网关

## 1.2 部署形态

当前实现是 FastAPI 单体服务：
- Web 客户端通过 Next.js 服务端代理访问后端
- 后端统一 API 前缀：`/api/v1`
- 外部依赖：PostgreSQL（必需），LLM/ASR 依赖按配置可选

## 1.3 主流程数据流

1. `POST /sessions/{id}/turns`
2. 读取并锁定 session 行（`SELECT ... FOR UPDATE`）
3. 解析输入（text 或 audio_ref -> ASR）
4. preprocess -> safety -> trigger -> policy/scaffold -> evaluation
5. 更新 `theta`、状态、next_action、question cursor
6. 同事务写入 turn + events + session 更新

## 1.4 鉴权与角色

- `candidate`：只能访问自己的 session
- `admin`：可访问 admin 配置与会话只读接口
- `annotator`：可写 annotation，且可调用 asr/nlp/safety/scaffold/evaluation 工具接口

token 由 `POST /auth/token` 签发，后端进行签名校验和角色校验。

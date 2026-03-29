# Contract: Phase 3 — 智能并发召回 API

## 完成标准

### Bug 修复 (随 Phase 3 提交)
- [ ] 1. `memory_worker.py` process_fact_extraction 在写入前检查 qdrant_id 是否已存在，跳过重复
- [ ] 2. `memory_worker.py` process_summary_generation 同上检查
- [ ] 3. Worker 不再因 UniqueViolation 进入 crash-loop

### RecallOrchestrator 服务
- [ ] 4. `recall_orchestrator.py` 存在于 `backend/app/memory/services/`
- [ ] 5. `QueryAnalyzer.analyze()` 接受 query string，返回 intent/entities/complexity，无 LLM 调用
- [ ] 6. QueryAnalyzer 从查询中提取文件路径（匹配 `/path/to/file` 或 `file.py` 模式）
- [ ] 7. QueryAnalyzer 从查询中提取错误信息（匹配 `Error:` / `Exception` / traceback 模式）
- [ ] 8. `RecallOrchestrator.recall()` 接受 query/user_id/agent_id/context_budget_tokens/timeout_ms
- [ ] 9. recall() 并发执行 Qdrant 向量搜索 + Neo4j 图遍历 + corrections 查询（asyncio.gather）
- [ ] 10. 每个并发任务有独立超时（Qdrant 3s, Neo4j 3s, corrections 2s），超时返回空而非 crash
- [ ] 11. 合并结果按优先级排序: corrections > high-score vectors > graph relations > summaries > facts
- [ ] 12. 内容去重（相同 content 只保留得分最高的）
- [ ] 13. 输出按 context_budget_tokens 截断（默认 2000 tokens，按字符估算 ~8000 chars）
- [ ] 14. Neo4j 不可用时 graceful degradation（跳过图遍历，其他源正常返回）

### POST /api/v2/recall 端点
- [ ] 15. `intelligent_recall.py` 存在于 `backend/app/api/memory/`
- [ ] 16. `POST /api/v2/recall` 接受 JSON body: `{user_id, query, agent_id?, context_budget_tokens?, timeout_ms?}`
- [ ] 17. 返回 `{context_text, sources[], query_analysis{intent, entities, complexity}, timing{total_ms, vector_ms, graph_ms}}`
- [ ] 18. `context_text` 为格式化的纯文本，可直接注入 agent system prompt
- [ ] 19. 端点在 `adapter_compat.py` 中注册到 `/api/v2/recall`
- [ ] 20. 缺少 user_id 或 query 返回 422

### 配置
- [ ] 21. `RECALL_VECTOR_TIMEOUT_MS` 配置项存在（默认 3000）
- [ ] 22. `RECALL_GRAPH_TIMEOUT_MS` 配置项存在（默认 3000）
- [ ] 23. `RECALL_DEFAULT_BUDGET_TOKENS` 配置项存在（默认 2000）

### 适配器升级
- [ ] 24. `adapters/claude-code/lib/api.sh` 新增 `recall_memories()` 函数调用 POST /api/v2/recall
- [ ] 25. `adapters/claude-code/mem0-retrieve.sh` 优先调用 recall，失败 fallback 到 search
- [ ] 26. `adapters/openclaw/provider.ts` 新增 `recall()` 方法
- [ ] 27. `adapters/openclaw/index.ts` before_agent_start 优先调用 `recall()`，失败 fallback 到 `search()`

### 文档
- [ ] 28. `docs/modules/memory.md` API 路由映射表包含 `POST /api/v2/recall`
- [ ] 29. `docs/modules/memory.md` 环境变量表包含 RECALL_* 配置
- [ ] 30. `.env.example` 包含 RECALL_* 配置项
- [ ] 31. `docs/modules/adapters.md` 协议说明更新（recall fallback 策略）

### 测试 + 质量
- [ ] 32. `make check` 通过
- [ ] 33. 现有 E2E 管道不回归
- [ ] 34. `curl POST /api/v2/recall` 返回有效 JSON，context_text 非空，timing 含 total_ms

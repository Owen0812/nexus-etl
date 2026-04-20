# Nexus ETL

Multi-Agent 智能文档处理管道，将原始文档（PDF / Word / HTML）转化为高质量向量化知识块，作为 RAG 系统的数据底层。

---

## 项目背景

传统文档预处理脚本存在三个核心痛点：

| 痛点 | Nexus ETL 解法 |
|---|---|
| 按字数盲目切块，语义断裂 | Semantic Chunker Agent（按语义边界切分） |
| 复杂 PDF（双栏/跨页表格/扫描件）解析失效 | Vision Extractor Agent（pdfplumber + Qwen-VL） |
| 每次全量重处理，成本高 | Increment Checker Agent（SHA-256 增量去重） |

---

## 系统架构

```
上传文件
   │
   ▼
Celery + Redis（异步任务队列）
   │
   ▼
┌─────────────────────────────────────────────────────────┐
│                  LangGraph StateGraph                   │
│                                                         │
│  increment_checker ──(重复)──► END                      │
│         │                                               │
│         ▼                                               │
│     orchestrator                                        │
│         │                                               │
│    ┌────┴─────────────┐                                 │
│    ▼    ▼    ▼        ▼                                 │
│ vision text word    html                                │
│ extractor extractor extractor extractor                 │
│    └────┬─────────────┘                                 │
│         ▼                                               │
│  semantic_chunker                                       │
│         ▼                                               │
│  metadata_tagger                                        │
│         ▼                                               │
│   quality_agent                                         │
│         ▼                                               │
│  embedding_writer ──► pgvector                          │
└─────────────────────────────────────────────────────────┘
```

---

## Agent 节点说明

| # | 节点 | 职责 |
|---|---|---|
| 1 | `increment_checker` | SHA-256 哈希去重，已处理文件直接跳过 |
| 2 | `orchestrator` | PDF 调 qwen-long 决策 vision/text 路径；Word/HTML 按扩展名直接路由 |
| 3 | `vision_extractor` | pdfplumber 提取文本+表格；复杂表格（行>10）调 Qwen-VL |
| 4 | `text_extractor` | 纯 pdfplumber 快速路径，跳过视觉模型 |
| 5 | `word_extractor` | python-docx 解析 .docx |
| 6 | `html_extractor` | BeautifulSoup + lxml 解析 .html/.htm |
| 7 | `semantic_chunker` | RecursiveCharacterTextSplitter（800 tokens, 100 overlap），表格块独立保留 |
| 8 | `metadata_tagger` | qwen-turbo 提取语言/关键词/内容类型；LLM 全失败时触发规则降级 |
| 9 | `quality_agent` | 规则评分（token 数/可打印率/重要性），阈值 0.4 过滤碎片 |
| 10 | `embedding_writer` | 批量 embed（每批 10 条）+ 写入 pgvector chunks 表 |

---

## 技术栈

| 层 | 技术 |
|---|---|
| Agent 框架 | LangGraph StateGraph + MemorySaver |
| 主力 LLM | Qwen-Long（编排/视觉分析） |
| 快速 LLM | Qwen-Turbo（元数据标注） |
| 视觉模型 | Qwen-VL-Max（复杂表格/扫描件） |
| Embedding | text-embedding-v3（dim=1024） |
| 异步队列 | Celery 5 + Redis 7 |
| 向量库 | PostgreSQL 16 + pgvector |
| 重排序 | BGE-Reranker（BAAI/bge-reranker-base，懒加载，无则降级） |
| 后端 | FastAPI + SQLAlchemy async + Alembic |
| 前端 | Next.js 14（App Router）+ Tailwind CSS |
| 可观测性 | Langfuse（全链路 LangGraph 追踪） |
| 容器化 | Docker Compose |

---

## 快速开始

### 前置要求

- Docker Desktop
- 阿里百炼 API Key（[申请地址](https://dashscope.aliyuncs.com)）

### 1. 克隆并配置环境变量

```bash
git clone https://github.com/Owen0812/nexus-etl.git
cd nexus-etl
cp .env.example .env
```

编辑 `.env`，填入必填项：

```env
QWEN_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
EMBEDDING_DIM=1024          # 必须与 pgvector 表定义一致
DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/nexus_etl
REDIS_URL=redis://redis:6379/0
```

### 2. 启动所有服务

```bash
docker compose up -d --build
```

启动后各服务端口：

| 服务 | 地址 |
|---|---|
| 前端 | http://localhost:3001 |
| 后端 API | http://localhost:8000 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

### 3. 使用

打开 http://localhost:3001，拖拽上传 PDF / Word / HTML 文件，在 Dashboard 页实时查看各 Agent 执行进度，处理完成后跳转结果页查看切块详情。

---

## 前端页面

| 路由 | 说明 |
|---|---|
| `/` | 文件上传（拖拽，支持 PDF / .docx / .html） |
| `/dashboard` | 实时进度面板（每 2s 轮询，节点级状态动画） |
| `/results/[documentId]` | 切块结果（统计卡 + ChunkCard 列表，含质量评分和实体 tags） |

---

## API 文档

### 文档管理

```
POST   /api/v1/documents/upload     上传文件，触发异步 ETL
GET    /api/v1/documents/           列出所有文档
GET    /api/v1/documents/{id}       查询单个文档状态
GET    /api/v1/documents/{id}/chunks  获取文档切块结果
```

### 任务状态

```
GET    /api/v1/pipelines/{task_id}  查询 Celery 任务进度（含每阶段完成情况）
```

### 混合检索

```
POST   /api/v1/search
```

请求体：

```json
{
  "query": "你的检索问题",
  "top_k": 5,
  "use_hyde": true,
  "document_id": "可选，限定在某文档内检索"
}
```

检索流程：HyDE 扩展 → text-embedding-v3 → pgvector 向量召回（Top-20）→ PostgreSQL BM25 全文召回（Top-20）→ RRF 融合 → BGE-Reranker 精排 → Top-K 返回。

---

## 项目结构

```
nexus-etl/
├── backend/
│   ├── agents/           # 10 个 LangGraph Agent 节点
│   │   ├── graph.py      # DAG 定义与路由逻辑
│   │   ├── state.py      # DocumentState TypedDict
│   │   ├── increment_checker.py
│   │   ├── orchestrator.py
│   │   ├── vision_extractor.py
│   │   ├── document_extractor.py   # word + html
│   │   ├── semantic_chunker.py
│   │   ├── metadata_tagger.py
│   │   ├── quality_agent.py
│   │   └── embedding_writer.py
│   ├── api/routes/       # FastAPI 路由
│   ├── models/           # SQLAlchemy 模型（documents / chunks / pipeline_runs）
│   ├── tasks/pipeline.py # Celery Task 入口（持久事件循环）
│   ├── utils/
│   │   ├── embeddings.py # text-embedding-v3 封装
│   │   └── reranker.py   # BGE-Reranker 懒加载
│   └── celery_app.py     # Celery 配置 + worker 持久事件循环
├── frontend/
│   └── src/
│       ├── app/          # Next.js App Router 页面
│       └── components/   # FileUpload / PipelineStatus
├── eval/                 # Evaluation Harness
│   ├── generate_fixtures.py
│   ├── metrics.py
│   ├── harness.py
│   └── report.py
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## Evaluation Harness

```bash
# 生成测试数据集（20 份合成 PDF）
python -m eval.generate_fixtures

# 运行端到端 benchmark
python -m eval.harness

# 生成报告（precision@k / recall@k / MRR / P50/P95/P99 延迟 / 吞吐）
python -m eval.report
```

---

## 环境变量说明

| 变量 | 必填 | 说明 |
|---|---|---|
| `QWEN_API_KEY` | ✅ | 阿里百炼 API Key |
| `EMBEDDING_DIM` | ✅ | 必须为 `1024`（text-embedding-v3 实际输出维度） |
| `DATABASE_URL` | ✅ | asyncpg 连接串 |
| `REDIS_URL` | ✅ | Redis 连接串 |
| `QWEN_MODEL` | | 主力模型，默认 `qwen-long` |
| `QWEN_VISION_MODEL` | | 视觉模型，默认 `qwen-vl-max` |
| `LANGFUSE_PUBLIC_KEY` | | Langfuse 追踪（可选） |
| `LANGFUSE_SECRET_KEY` | | Langfuse 追踪（可选） |


## License

MIT

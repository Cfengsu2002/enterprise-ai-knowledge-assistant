# Enterprise AI Knowledge Assistant

An enterprise-grade AI knowledge assistant that enables users to search, retrieve, and interact with internal documents using natural language.

This project is designed to help organizations unlock the value of their internal knowledge base by combining **Large Language Models (LLMs)**, **semantic search**, and **Retrieval-Augmented Generation (RAG)**. Instead of manually searching through large volumes of documentation, users can ask questions in plain English and receive relevant, grounded, and context-aware answers.

The system is built with a modular architecture so that it can be extended to support different embedding models, vector databases, LLM providers, and document ingestion workflows.

---

## Table of Contents

- [Overview](#overview)
- [Problem Statement](#problem-statement)
- [Solution](#solution)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [RAG Pipeline](#rag-pipeline)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [Installation](#installation)
- [Environment Variables](#environment-variables)
- [Running the Project](#running-the-project)
- [Document Ingestion](#document-ingestion)
- [API Endpoints](#api-endpoints)
- [Example Workflow](#example-workflow)
- [Example Queries](#example-queries)
- [Design Decisions](#design-decisions)
- [Challenges](#challenges)
- [Future Improvements](#future-improvements)
- [Use Cases](#use-cases)
- [Security Considerations](#security-considerations)
- [Testing](#testing)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Enterprise teams often store important knowledge across many different sources such as PDFs, internal wikis, onboarding documents, engineering notes, HR policies, product documentation, and meeting summaries. As the volume of information grows, it becomes difficult for employees to quickly locate accurate answers.

This project solves that problem by providing a natural language interface over enterprise knowledge. Users can ask questions such as:

- "What is the company policy on remote work?"
- "How does the onboarding process work for new engineers?"
- "What are the main responsibilities of the support team?"
- "Summarize the incident response guide."

The assistant retrieves the most relevant document chunks from the knowledge base and uses an LLM to generate a final answer grounded in those sources.

---

## Problem Statement

Traditional keyword-based search systems often struggle in enterprise environments for several reasons:

1. Important information is spread across many documents.
2. Exact keyword matches may not capture meaning.
3. Employees may not know the correct terminology used in internal docs.
4. Long documents make manual reading slow and inefficient.
5. Internal knowledge changes over time and becomes hard to manage.

As a result, employees waste time searching for information, duplicate work, or rely on incomplete answers.

---

## Solution

The Enterprise AI Knowledge Assistant uses a **Retrieval-Augmented Generation (RAG)** workflow to improve answer quality and relevance.

The system works in several steps:

1. Enterprise documents are collected and processed.
2. Documents are split into smaller chunks.
3. Each chunk is converted into an embedding vector.
4. Embeddings are stored in a vector database.
5. When the user asks a question, the query is embedded.
6. The system retrieves the most relevant chunks.
7. The LLM uses those retrieved chunks to generate a final response.

This approach helps reduce hallucination and keeps answers grounded in actual company documents.

---

## Key Features

### 1. Natural Language Question Answering
Users can ask questions in plain English instead of manually browsing documents.

### 2. Retrieval-Augmented Generation (RAG)
The system retrieves relevant context before generating an answer. This improves factual grounding.

### 3. Semantic Search
The assistant searches by meaning, not only by exact keyword matches.

### 4. Document Ingestion Pipeline
Supports loading and indexing enterprise documents into the knowledge base.

### 5. Summarization
Users can request concise summaries of long internal documents.

### 6. Modular Architecture
The project is structured so different models, vector stores, and ingestion tools can be swapped easily.

### 7. Scalable Backend API
A backend API exposes endpoints for querying, ingestion, and health checks.

### 8. Enterprise Use Case Focus
The system is designed for internal company knowledge, support workflows, and employee productivity.

---

## System Architecture

The project follows a standard enterprise AI assistant architecture.

```text
                    +----------------------+
                    |   Enterprise Docs    |
                    | PDFs / Docs / Notes  |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Document Processing   |
                    | Clean / Chunk / Parse |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Embedding Model       |
                    | Convert text to vecs  |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Vector Database       |
                    | Store embeddings      |
                    +----------+-----------+
                               |
                               v
+---------+        +----------------------+        +----------------------+
|  User   | -----> | Backend Query Layer  | -----> |   LLM Response Gen   |
| Query   |        | Retrieve top-k docs  |        | Answer with context   |
+---------+        +----------------------+        +----------------------+
                               |
                               v
                    +----------------------+
                    | Final Grounded Answer |
                    +----------------------+

---

## 文件存储模型（S3 + 数据库）

- **S3**：只存放**源文件**二进制（分片上传完成后合并为完整对象）。
- **PostgreSQL `documents` 表**：存放**指向对象的链接**（`file_path`，如 `s3://bucket/key`）以及 **元数据**：
  - `storage_type`：`local`（本地上传目录）或 `s3`
  - `original_filename`、`content_type`、`byte_size`
  - `s3_bucket`、`s3_key`（S3 时便于查询/拼接 URL）
  - `file_metadata`（JSONB，如 `aws_region`、`source_uri` 等扩展字段）

本地直传 `/upload` 仍写入磁盘，`file_path` 为相对路径，`storage_type=local`，同样会记录 `original_filename`、`byte_size` 等。

已有数据库需执行 `database/init/007_documents_storage_metadata.sql`（或在新库中随 `docker-compose` 的 init 脚本自动应用）。

### 使用 AWS S3 时你要准备什么（不用在聊天里发密钥）

在项目根复制 `.env.example` → `.env`，**只在你本机或 CI/服务器**里填写：

| 变量 | 说明 |
|------|------|
| `S3_BUCKET` | 桶名（与控制台一致） |
| `AWS_REGION` | 桶所在区域，如 `ap-northeast-1` |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | 给**后端**用的 IAM 用户密钥；或改用 EC2/ECS **IAM 角色**（容器内可不设这对变量） |
| **不要设** `S3_ENDPOINT_URL` | 走真实 AWS 时留空 |

后端需要对该桶（或前缀 `enterprises/*`）具备：`s3:CreateMultipartUpload`、`s3:UploadPart`、`s3:CompleteMultipartUpload`、`s3:AbortMultipartUpload`、`s3:ListParts`（以及若你后续要读对象再开 `GetObject`）。

**桶 CORS（浏览器直传分片必填）**：在 S3 控制台 → 该桶 → Permissions → CORS，例如本地开发：

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["PUT", "GET", "HEAD"],
    "AllowedOrigins": [
      "http://localhost:5173",
      "http://127.0.0.1:5173"
    ],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3000
  }
]
```

上线时把 `AllowedOrigins` 改成你的前端域名。**必须暴露 `ETag`**，否则前端拿不到分片 ETag，无法 `CompleteMultipartUpload`。

> **注意**：AWS 控制台 **不支持** 在 `ExposeHeaders` 里写通配符（如 `x-amz-*`），保存会报错。分片上传只需暴露 **`ETag`** 即可，不要加 `x-amz-*`。

> **AllowedOrigins**：必须与浏览器地址栏 **完全一致**（含 `http`/`https`、主机名、端口）。`http://localhost:5173` 与 `http://127.0.0.1:5173` 是两条不同 Origin；若用 Docker 映射到 `8080` 等，请把对应 Origin 也写进 CORS。

> 前端对 S3 的预签名 PUT 使用 **ArrayBuffer** 作为 body，避免 `Blob` 自动带上 `Content-Type`（如 PDF）导致与预签名不匹配、S3 返回 403；在浏览器里有时表现为 `Failed to fetch`。

> **仍出现 `Failed to fetch`？** 前端会在直连 S3 失败时 **自动改走** `POST /upload/s3/multipart/part`（经同源 `/api` 把分片交给后端，由后端调用 S3 `UploadPart`，**不依赖桶 CORS**）。若希望始终走代理，可设 `frontend/.env`：`VITE_S3_UPLOAD_VIA_PROXY=true` 后重启前端。

**Docker**：`docker-compose.yml` 中 `backend` 已配置 `env_file`（`.env` **可选**，无文件也能启动；需要 S3 时复制 `.env.example` 为 `.env` 并填写）。`DATABASE_URL` 在 compose 里固定为连容器 `db`。执行 `docker compose up --build`。

**`init failed: 500`（或步骤 1/4）**：多为 Postgres 未建 **`multipart_upload_sessions`（`database/init/006_*.sql`）** 或 **`enterprises` 里没有对应 `enterprise_id`**。更新代码后重启后端，界面会显示后端返回的**具体错误**（如 `relation does not exist` / `foreign key`）。

**`Key (enterprise_id)=(1) is not present in table "enterprises"`**：库里还没有 `id=1` 的企业。新库会在 **`008_seed_demo_enterprise.sql`** 里自动插入 `Demo Enterprise`；**已有**库请手动执行：  
`INSERT INTO enterprises (id, name) VALUES (1, 'Demo Enterprise') ON CONFLICT (id) DO NOTHING;`  
（若 `id=1` 已被占用，请在前端改用实际存在的 Enterprise ID，或改用别的 `id` 并同步改前端默认值。）

你配置好后无需把 Access Key 发给任何人；若某一步报错（403 CORS、SignatureDoesNotMatch 等），把**报错原文**（可打码密钥）贴出来即可排查。

### 自动化测试（S3 分片 + ListParts / 续传逻辑）

使用 [moto](https://github.com/getmoto/moto) 模拟 S3，**不消耗真实 AWS**，验证预签名 PUT、`ListParts`（断点续传查询）、`CompleteMultipartUpload`：

```bash
pip install -r requirements-dev.txt
PYTHONPATH=. pytest tests/test_s3_multipart_moto.py -v
```

### 如何测试「真实 AWS S3」是否跑通

1. **`.env`（与 `docker-compose` 同目录）**  
   - `S3_BUCKET` = 你的桶名（勿用占位符）  
   - `AWS_REGION` = 桶所在区域（须一致）  
   - `AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY` **两行都不能留空**  
   - 保存后执行：`docker compose up -d --build`（让 `backend` 容器重新读入环境变量）

2. **自检容器里是否有密钥（不打印内容）**  
   ```bash
   docker compose exec backend sh -c 'test -n "$AWS_ACCESS_KEY_ID" && test -n "$AWS_SECRET_ACCESS_KEY" && echo OK || echo MISSING'
   ```  
   若输出 `MISSING`，说明 `.env` 未生效或变量名为空。

3. **自检数据库**  
   - 已执行 `database/init/006_multipart_upload_sessions.sql`（`multipart_upload_sessions` 表存在）  
   - `enterprise_id` 在 `enterprises` 表里存在（否则插入 session 会失败）

4. **API 探针（`enterprise_id` 改成你库里有的）**  
   ```bash
   curl -s -X POST "http://localhost:8000/upload/s3/multipart/init" \
     -H "Content-Type: application/json" \
     -d '{"enterprise_id":1,"filename":"probe.txt","file_size":64,"title":"probe"}'
   ```  
   - 成功：返回 JSON，含 `session_id`、`upload_id`、`key`、`bucket`  
   - `503` 且提示凭证：回到步骤 1～2  
   - `502` 且 S3 错误码：检查桶名、区域、IAM 权限（`CreateMultipartUpload` 等）

5. **浏览器端到端**  
   打开 `http://localhost:5173`，选小文件，点「上传 / 续传」。桶须配置 **CORS**（含 `ExposeHeaders: ETag`），见上文 JSON。

**若页面报 `Failed to fetch`、但 `Fetch enterprise` 正常**：多为浏览器跨端口访问 `localhost:8000` 被拦截。已默认在开发模式用 **同源 `/api` + Vite 代理**（见 `frontend/vite.config.js`）。请 **`docker compose up -d --build`** 重建前端，并删掉 `frontend/.env` 里多余的 `VITE_API_URL`（或设 `VITE_USE_API_PROXY=false` 仅当你刻意直连 8000 时）。

# DeepSeek / CUDA 可选适配说明

此实现从 2026-10-14 用户提供的真实部署源码中整理，只新增后端选择与受控测试；默认 Ollama 路径仍可用。

## 设置

在 GPU 服务器的私有环境中安装：

~~~sh
python -m pip install -e '.[real,local,nli,eval]'
~~~

私有 .env（**不可上传密钥**）需要设置：

~~~dotenv
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-flash
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=<填写自己的 API Key>
EMBEDDING_BACKEND=sentence_transformers
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024
EMBEDDING_DEVICE=cuda
NLI_DEVICE=cuda
VERIFIER_BACKEND=nli
LLM_MAX_ASYNC=2
~~~

首次下载向量 / NLI 模型需要外网与磁盘空间。LightRAG 的持久化索引必须与 embedding 模型版本、归一化与维度一致；**不要直接混用原 Ollama 向量索引和 CUDA 本地模型索引**。

## 代码行为

- DeepSeekClient 是 OpenAI 兼容 /chat/completions 调用，支持在返回内容为空或因 token 限额截断时重试；生成与图谱抽取使用同一鉴权来源。
- DeepSeekGenerator 使用返回的 answer/claims JSON，配合 verify/full 的答案锚点检查。
- LightRAGRetriever 可以选 sentence-transformers 本地 CUDA embedding，并对维度进行校验。
- 插入文档时将层级路径编码进文件 ID，避免某些上游索引以 basename 去重；返回证据时解码。
- NLI_DEVICE 可选 cuda；不设置默认 cpu。
- API 使用记录不包含正文和密钥，但包含用量与运行信息；该日志应保留在私有目录中。

## 验证边界

GitHub Actions 仅通过 mock HTTP 请求及伪 LightRAG 对象测试接口契约，不会实际访问 DeepSeek、加载 GPU 模型或完整建图。

**不能因此宣布已复现 2026-10-14 的真实模型准确率。** 正式实验需在原始 CUDA / DeepSeek 环境中核对上游 LightRAG 版本、数据快照与索引，重新跑独立验证集并报告新结果。

注意不同 DeepSeek 模型的 API 参数可能变化，若服务端拒绝 thinking/response_format，需依据当时官方协议调整，并重新执行集成测试。

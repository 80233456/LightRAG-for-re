# EvidenceChain-RAG · 证据链可信问答系统（可运行 V0.1）

面向 2026 年全球校园人工智能算法精英大赛的独立参赛研发骨架。基于 **HKUDS LightRAG** 的结构化检索 SDK，添加两个**待实验验证的候选方法**：`AdaptiveController`（预算控制）与 `EvidenceVerifier`（声明级支持/冲突验证、选择性拒答）。

> **重要：本仓库是初赛用研发骨架，不是已证明具备国奖性能的成品。** `demo` 是离线假检索/假生成，仅用于 CI 与模块冒烟；所有论文/比赛性能数字必须来自 `lightrag + Ollama + NLI` 的真实实验。

## 一分钟启动（离线，不下模型）

```bash
# 在项目根目录，推荐 Python 3.11
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e '.[test]'
cp .env.example .env   # Windows: copy .env.example .env
python scripts/run_demo.py ask --backend demo --variant full
python -m pytest -q
```

离线 `demo` 模式自动加载 `data/demo/documents.jsonl`。预期能输出 `question / answer / candidate_answer / evidence / verification / retrieval / latency_ms` 等 JSON 字段。此结果不能用于参赛论文跑分。

## 接入真实 LightRAG（推荐 Ubuntu + NVIDIA GPU）

```bash
# 安装 Ollama：https://ollama.com/download 并启动其服务
ollama pull qwen2.5:7b
ollama pull bge-m3
# 安装项目的真实检索扩展
python -m pip install -e '.[real,test]'
cp .env.example .env
python scripts/check_environment.py

# 建立持久化索引（首次可能较慢，需要模型做实体关系抽取）
python scripts/run_demo.py ingest --backend lightrag --docs data/demo/documents.jsonl
# 查询已存在的持久化索引
python scripts/run_demo.py ask --backend lightrag --variant baseline --question '星桥项目于哪一年在什么城市启动？'
python scripts/run_demo.py ask --backend lightrag --variant full --question '星桥项目于哪一年在什么城市启动？' --verifier lexical
```

需要模型层级的证据判断时安装并使用 `NLI`：

```bash
python -m pip install -e '.[nli]'
python scripts/run_demo.py ask --backend lightrag --variant full --verifier nli --question '星桥项目于哪一年在什么城市启动？'
```

`lexical` 只是开发模式的规则验证，绝对不要用该成绩宣称语义可信性。NLI 模型约 279M 参数，CPU 也能跑但较慢；阈值需要在独立验证集上调整，不得按测试集调阈值。

若显存不够，可尝试 `ollama pull qwen2.5:3b` 并把 `.env` 的 `LLM_MODEL` 改为 `qwen2.5:3b`。所有对照组必须使用同一生成模型。

**禁止中途更改 embedding 模型维度然后继续使用同一个索引目录**：改变 embedding 模型/维度应新建 `LIGHTRAG_WORKDIR`，重新索引并记录版本。

## 项目目录

```text
EvidenceChain-RAG/
├── .env.example
├── .gitignore
├── .github/workflows/tests.yml
├── README.md
├── LICENSE
├── pyproject.toml
├── configs/
│   ├── experiment_matrix.json
│   ├── upstream_revisions.json
│   └── multihop_split_indices.json  # 已冻结的随机种子划分
├── data/
│   └── demo/documents.jsonl
├── docs/
│   ├── algorithm_design.md
│   ├── technical_report_outline.md
│   └── submission_checklist.md
├── results/                       # 真实评测后写入 JSON，不附虚构数据
├── scripts/
│   ├── run_demo.py                # 离线/真实模型CLI
│   ├── check_environment.py
│   ├── make_holdout.py
│   ├── eval_ragbench.py
│   └── eval_multihop.py
├── src/evidencechain/
│   ├── __init__.py
│   ├── config.py
│   ├── schema.py
│   ├── retrievers.py            # DemoRetriever / LightRAGRetriever
│   ├── generation.py           # DemoGenerator / OllamaGenerator
│   ├── adaptive.py             # 候选创新点 A
│   ├── verifier.py             # 候选创新点 B
│   ├── pipeline.py             # baseline / adaptive / verify / full
│   ├── factory.py
│   └── metrics.py
└── tests/
    ├── test_adaptive.py
    ├── test_metrics.py
    ├── test_pipeline.py
    └── test_verifier.py
```

## 两个候选算法的实现位置

**A：风险感知检索控制** → `src/evidencechain/adaptive.py`

- baseline：`mix` 模式，最多取 8 个 chunk。
- adaptive：先 `naive` 取 4 个；若问题有多跳/比较信号或首轮检索覆盖度偏低，再 `mix` 扩展，去重后最多保留 8 个。
- 记录 `modes, calls, risk, coverage, contexts_seen`，用于**质量–成本**消融。
- 当前仅为规则控制器。投稿级算法新颖性和收益尚未通过对比证明。

**B：声明级证据验证** → `src/evidencechain/verifier.py`

- LLM 返回 JSON：`answer` 和 1–3 条可检验的 `claims`。
- 将检索证据拆成适度窗口，计算各声明相对各证据的 `entailment` 和 `contradiction` 分数。
- `supported / refuted / conflict / insufficient` 四类；**所有声明被支持才发布答案**，否则拒答并保留审计记录。
- 分数不是概率校准后的可靠性概率。claim 生成的遗漏可能使验证器漏检，应单独评估。

详细设计在 `docs/algorithm_design.md`。

## RAGBench：支持判断实验（不可报告为 QA 准确率）

使用原始 `documents + response` 及 `overall_supported`，计算二分类 Accuracy / Precision / Recall / F1、错误接受率。建议先用验证集测试流程，再锁定阈值只评估测试集一次。

```bash
python -m pip install -e '.[eval,nli]'
# 快速流程检查（lexical，科学实验中不可作为模型算法成果）
python scripts/eval_ragbench.py --config covidqa --split validation --limit 30 --verifier lexical --output results/ragbench_smoke.json
# 真实 NLI 验证实验（建议使用固定样本序列和验证集调阈值）
python scripts/eval_ragbench.py --config covidqa --split validation --limit 100 --verifier nli --output results/ragbench_val.json
# 阈值冻结后测试；limit 设置为该 config 的全部行数才可称完整测试
python scripts/eval_ragbench.py --config covidqa --split test --limit 100000 --verifier nli --output results/ragbench_test.json
```

需要注意：RAGBench 由多个子数据集组成，不同 config 的样本数量与标签覆盖不同，不应拼凑成一个数据集指标。

## MultiHop-RAG：多文档问答和证据匹配实验

使用 Hugging Face 上的 **两个配置**：`corpus` 与 `MultiHopRAG`。正式实验**完整 corpus 必须入库**，并固定提问索引（数据卡没有独立的官方 `test` split）。

```bash
# 1. 冻结问题划分（先于调整算法/看测试结果）
python scripts/make_holdout.py --n 2556 --seed 20261014

# 2. 先用 20 个问题检查评测入口，建立完整语料索引
python scripts/eval_multihop.py --backend lightrag --index --portion pilot --limit-queries 20 --variant all --verifier nli --output results/multihop_pilot.json

# 3. 验证集（不要加 --index，重用已持久化索引）
python scripts/eval_multihop.py --backend lightrag --portion validation --split-file configs/multihop_split_indices.json --limit-queries 511 --variant all --verifier nli --output results/multihop_val.json

# 4. 测试集，冻结配置后再进行（limit >= 测试题数）
python scripts/eval_multihop.py --backend lightrag --portion test --split-file configs/multihop_split_indices.json --limit-queries 10000 --variant all --verifier nli --output results/multihop_test.json
```

如想**仅排障**，可 `--backend demo --max-corpus 20 --portion pilot --limit-queries 5 --verifier lexical`；这会更改检索语料，**绝不用于正式对比**。

返回的 `fact_recall_at_selected_k` 是按规范化原文子串计算的**证据事实匹配代理指标**（strict match），不等于语义层面 Recall@K。另记录 EM、token F1、拒答覆盖率、检索次数和探索性的平均时延。测试集不得被用于选择阈值或调参。

**注意速度**：图谱入库涉及 LLM 实体抽取，上百文档可能耗时很久。必须尽早启动完整索引，并预留重试、断点恢复和验收时间。

## 实验质量底线

1. 先 `python -m pytest -q`，再真实运行所有版本。
2. 记录 `pip freeze`、`ollama list`、GPU/CPU、Python 和 LightRAG commit；保存每组详细 JSON。
3. 固定同一 LLM、embedding、NLI 与数据划分；报告中写明**缓存命中和启动条件**。
4. 阈值 `SUPPORT_THRESHOLD`、`CONTRADICTION_THRESHOLD` 仅从验证集选取；勿在测试集试错。
5. 提供原作者引用。项目源码许可不覆盖外部数据与模型，请检查各自 license。
6. 10月30日前交付最小真实系统、初步四组结果和一份完整报告。模型没有跑通时，不得使用 `demo` 结果替代。

## 上游与公开数据来源

- LightRAG（MIT）：https://github.com/HKUDS/LightRAG
- LightRAG Python SDK docs：https://github.com/HKUDS/LightRAG/blob/main/docs/ProgramingWithCore.md
- RAGBench（CC BY 4.0）：https://huggingface.co/datasets/galileo-ai/ragbench
- MultiHop-RAG（ODC-BY）：https://huggingface.co/datasets/yixuantt/MultiHopRAG
- mDeBERTa NLI：https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-mnli-xnli
- Ollama：https://ollama.com/

本仓库中 `src/evidencechain` 是独立研发的适配与算法候选实现，不宣称其上游工作属于团队原创。正式作品须遵守当届赛项的提交材料、引用披露与使用许可规则。

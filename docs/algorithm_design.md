# 算法设计说明（V1 候选方案，未经性能验证）

## A. 风险感知自适应检索（src/evidencechain/adaptive.py）

研究问题：固定检索深度可能浪费资源或漏掉多跳证据。V1 使用易复现的规则策略：

1. 默认从 LightRAG 的 `naive` 模式取得最多 4 个 chunk。
2. 对问题计算先验复杂度风险 `r(q)`，并计算问句 token 在检索 chunk 中的词汇覆盖 `c(q,D)`。
3. 当 `r(q) >= 0.43` 或 `c(q,D) < 0.30`，再从 `mix` 模式扩展检索最多 8 个 chunk，按 `(source,content)` 去重。
4. 最多保留 8 条证据。保存调用次数、检索模式、首轮覆盖度与总时延。

当前 `r(q)` 是固定阈值的启发式控制器，是**研发基线**而非已经学习得到的策略。下一阶段：用验证集学习风险预测与检索预算策略，目标可写为：

`argmax_policy E[faithfulness] - λ * E[retrieval_cost] - μ * E[latency]`

必须展示与 `mix@8`、`naive@8`、`mix@16` 的成本质量曲线，才可以论证所提策略具有优势。当前代码仅内置 `mix@8` 完整消融对照，额外 `naive@8`、`mix@16` 应添加在正式论文实验中。

## B. 声明级证据验证与拒答（src/evidencechain/verifier.py）

1. 使用固定的 JSON 输出格式取得 `answer` 与 1–3 条完整陈述 `claims`。
2. 对检索文本分窗，逐一计算 `NLI(premise=evidence, hypothesis=claim)` 的 entailment 和 contradiction 分数。
3. 每个声明取最大支持分数 `S` 与最大矛盾分数 `C`；若 `S >= τ_s` 且 `C >= τ_c` → `conflict`；仅矛盾达阈值 → `refuted`；仅支持达阈值 → `supported`；否则为 `insufficient`。
4. **所有声明 supported** 才允许输出，否则返回空答案、保存候选答案与证据审计结果。
5. 模型 softmax 分数**不是经过概率校准的可信度**；应在验证集调阈值，配合可靠性图、风险—覆盖率曲线做校准。

重要局限：V1 采用生成模型提供的 claims；若模型遗漏关键断言或把问题改写错误，会造成验证盲点。国赛阶段应加入 claim coverage / claim extraction 人工标注集，检查每一条答案的全覆盖验证率。

## C. 受控实验设计

- 四组：baseline / adaptive / verify / full；确保语料、模型、解码温度、版本相同。
- RAGBench：对数据集中现成的 `response` 和 `documents` 做标签预测，与 `overall_supported` 比较 P/R/F1；**不能报告为端到端问答正确率**。验证集调阈值，测试集只评估一次。
- MultiHop-RAG：先索引**完整 corpus**；运行 `make_holdout.py` 固定 `dev/validation/test` 问题索引；严格保留测试集。报告 token F1、EM、事实严格匹配召回代理指标（非语义 retrieval recall）及有效回答覆盖率。
- 建议将 `fact_recall_at_selected_k` 命名为 `evidence_string_recall_proxy`（V1 JSON 键名为前者），不可夸大为人工判断的文档召回率。
- 消融应控制 Token 开销、模型和随机种子；如果比较时延，应记录冷启动/热启动、缓存开关、硬件和并发，最好每组隔离运行并报告 P50/P95。V1 给出的单次调用延时仅用于排障。
- 自建 conflict 样本：由人工双人交叉标注，每例附支持/反驳证据；不得根据测试结果修改阈值。

## D. 原创归属划分

| 部分 | 来源 | 可以声称的工作 |
|---|---|---|
| 图谱检索/实体抽取/索引 | HKUDS LightRAG | 引入并复现，不属于团队原创 |
| Ollama/BGE-M3/NLI | 外部模型 | 集成，不属于团队原创 |
| 风险估计与预算控制 | 本项目 `adaptive.py` | 规则控制算法候选；需证明优于固定检索 |
| 冲突识别、阈值拒答与审计 | 本项目 `verifier.py` | 验证策略候选；需证明有独立贡献 |
| 数据划分与消融实验 | 本项目 | 可复现实验工程 |

代码原创性 ≠ 学术方法新颖性。正式提交前须做同类论文与开源检索（Adaptive RAG、Self-RAG、CRAG、RAGAS、RAGBench、citation verification），明确和已有方法的差异。

# EvidenceChain RAG 复核：剩余风险与评估修复

检查日期：2026-10-15。范围：GitHub main 的检索、验证、生成、评估管线及先前上传的 2026-10-14 真实实验交付包。

## 这一轮可确定并已提交修复的工程问题

1. RAGBench 脚本曾读取 row["overall_supported"] 而未读取真实 test parquet 使用的 adherence_score。旧 GitHub 脚本会跳过样本，甚至在无标签时触发指标计算错误。已加入 support_label 并为 True/False/缺失/错误类型添加测试。上传实验包的 manifest 明确标注 target_column=adherence_score。
2. GitHub 的 NLIModelScorer 已支持 device="cuda"，但 factory.py 和 config.py 未提供参数透传，导致默认 CPU 推理。已加入 NLI_DEVICE 环境参数，默认 cpu，显式设置 cuda 时从 factory 传给模型；是否实际使用 GPU 仍需在 GPU 服务器上验证。
3. Github eval_multihop.py 原来每个 variant 独立生成答案，即使问题与证据完全相同，也会重复请求生成模型，增加费用并让验证器消融受到生成随机性干扰。已加入按“问题 + 有序证据 ID/来源/文本”缓存候选答案，评估期间只复用完全相同的输入（不会使用 gold）。若证据不同不复用。

## 还发现的算法问题，尚未贸然改判定规则

### P0：answer 与 claims 可能不一致

管线目前按 claims 是否通过 NLI 决定是否发布 answer，**没有验证最终 answer 是否受这些 claims 蕴含**。例如证据与 claims 都说“南京”，生成器却把 answer 填成“北京”，NLI 仍会放行，因为它根本没有检查 answer 本身。

这是可用固定生成器与 LexicalScorer 本地复现的逻辑漏洞。应设计 answer→claim 一致性约束并单独评估误拒答；仅强制 answer 是 claims 的字面子串可能伤害别名、日期规范化等有效答案，不建议直接加粗糙规则。

### P1：多实体声明可能被过滤得一条证据不剩

entity_anchors() 从 claim 中找出所有包含数字的 ID，_windows() 要求同一文档片段里拥有 **所有 ID**。跨文档多跳的声明一旦提到两个实体（例如 Aster-01-7255 与 Beryl-02-1000），即使两个来源各自可靠，也可能完全无法进入 NLI。使用固定 AlwaysSupports 验证器可复现，当前返回 insufficient。

需要根据原子事实分解、关系类型和跨文档推理来评估，而不应该简单把无关文档合并为“已证明”。

### P1：自适应扩展不是严格意义的多跳检索

adaptive.py 只是对**同一问题**再次执行 mix@16，合并旧 mix@8 的前 8 条与新增条目。它可能取到更多材料，但没有根据第一跳发现的实体改写查询或补找缺失关系；增加费用不保证回答更准确。

建议新增“缺失关系槽位 → 目标实体查询改写 → 跨文档证据链”的候选策略，与 mix@8、mix@16 和当前自适应做消融。

### P0：公开 GitHub 与服务器部署未同步

上传实验包的 deployed_source 包含 DeepSeek API、CUDA bge-m3 等代码；公开 GitHub factory/retrievers/generation 仍主要使用 Ollama。两者不可被视为相同运行实现。**不要直接用 GitHub 当前命令声称复现 DeepSeek+CUDA 实验。**

同步部署端版本时必须先锁定上游 LightRAG API、记录环境、补充集成测试，不能盲目覆盖已有修复。

### P1：验证器阈值尚未校准

0.78/0.70 是经验阈值，旧 RAGBench 的支持类召回率低。之前修复只改善实体对齐和证据覆盖，不等于新版本在真实 NLI 上已有质量收益。真正多跳声明仍可能需要组合证据而非单个窗口判定。

## 建议下轮优先级

1. 先验证并修正 answer/claims 一致性，确保不会错误放行。
2. 拆分多实体原子事实并增设多来源组合验证，不要只靠 ID 的全量同窗过滤。
3. 将完整 DeepSeek / CUDA 适配从真实部署工件审计后同步，并做 GPU 集成检查。
4. 最后在验证集上定参数，冻结版本，在新盲测题上按组比较 EM、误拒答/错误接受、覆盖率、成本与时延。

## 关于测试

单元测试和 GitHub Actions 可以证明代码符合这些测试场景，不能代替 4090 环境的真实 LightRAG + DeepSeek + NLI 运行。既有 MultiHop dev20 成绩是旧版本数据，不能据此计算修复后的正确率。

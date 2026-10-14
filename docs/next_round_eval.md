# 下一轮评估方案与离线历史审计

本文件将旧实验记录、新版离线诊断和将来真实模型评估严格区分。

## 1. 历史数据检查（不调用模型）

安装测试依赖，然后提供用户保留的原始 ZIP：

~~~sh
python -m pip install -e '.[test]'
python scripts/offline_audit_archive.py /path/to/evidencechain_experiment_20261014.zip --output results/offline_audit_20261014.json
~~~

该脚本直接读取封存的 2026-10-14 实验记录。它不调用 DeepSeek、不检索新证据、不重新运行 NLI，因此不是修复版性能测试。

历史 MultiHop dev20：baseline EM=60%，adaptive=55%，verify/full=25%，后二组完全拒答。历史 onsite test45：baseline=88.89%，adaptive=84.44%，verify/full=40%，后二组完全拒答。

新版自适应控制器面对 **旧 baseline 的 mix@8 证据**，20 道 MultiHop 中预计 12 道触发扩展，8 道不触发。这里只统计旧证据上的触发判定，不是实际检索调用次数、回答质量或新正确率。

## 2. 新一轮真实评估步骤

1. 在 GPU 环境中确认原 LightRAG 完整持久化索引、模型版本、API 模型、提示词及检索配置，并记录 commit SHA。
2. 对照上传的服务器交付源码：其中有额外的 DeepSeek / CUDA 适配，**不能假定 GitHub 当前源文件已与服务器完全一致**。运行前必须同步并验收。
3. 先用已冻结的 validation_indices 评估误拒答、错误接受与覆盖率；仅允许在验证集上决定阈值或策略。
4. 冻结模型、阈值、检索预算、代码版本，最后只对独立的 test_indices 做一次正式评价。
5. 同条件比较 baseline / adaptive / verify / full，分别报告 EM、可回答题 EM、拒答率、错误接受率、检索调用次数、tokens，以及支持分类 Precision/Recall/F1。
6. 不要利用旧测试成绩反复修改模型后仍把同一测试集称作盲测集。

仓库已有 MultiHop 评估入口；在完整原模型运行环境准备好后，可使用：

~~~sh
python scripts/eval_multihop.py --backend lightrag --verifier nli --variant all --portion validation --split-file configs/multihop_split_indices.json --limit-queries 100 --output results/new_validation100.json

# 验证集优化结束、配置冻结以后再运行独立测试：
python scripts/eval_multihop.py --backend lightrag --verifier nli --variant all --portion test --split-file configs/multihop_split_indices.json --limit-queries 100 --output results/new_test100.json
~~~

上述命令依赖已部署的真实模型和索引；当前离线 GitHub Actions 不能替代真实运行。若 GitHub 与服务器的 LLM 适配器尚未同步，上述 CLI 不应宣称复现了原 DeepSeek API 实验。

RAGBench 给出的 adherence_score 是证据支持标签，不是 QA 正确率；必须单独报告这类评估。

## 3. 仍需处理的算法局限

- 字符串实体锚点不能完整解决别名、代词、中文自由实体和不同时间属性的对齐。
- 当前每个 NLI 输入仍只处理一个文本窗口与一条声明；真正的多跳答案可能需要跨文档**组合证据**。这项局限还未修复。
- 增加检索条数和触发次数未必提升正确率，必须同时评估负面证据干扰及费用。
- 全部拒答也可能因为 null_query 获得表面 EM，必须公布可回答题正确率和覆盖率。
- 历史缓存命中后的运行时延不能代表新模型时延或成本。

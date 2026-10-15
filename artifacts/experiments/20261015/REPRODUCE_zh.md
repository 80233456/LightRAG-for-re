# V2 运行与复核

## 服务器直接问答

新版本独立部署于 `/root/autodl-tmp/evidencechain_v2_20261015`，没有覆盖旧算法。
下列入口使用既有私有配置，默认完整流程；问题请替换为自己的实际问题。

```bash
/root/autodl-tmp/evidencechain_run_20261014/venv/bin/python \
  /root/autodl-tmp/evidencechain_v2_20261015/ask_v2.py \
  'Your question'
```

可增加 `--variant context_only` 或 `--variant verify` 运行消融分支。
输出包括最终答案、原候选、证据全文、引用、验证报告、重试记录和字符偏移。
交互问答的API用量写入单独日志，不混入冻结实验成绩。

现有609篇MultiHop-RAG文档的图索引与本地BGE权重已在服务器，下载包不含这些大文件。
DeepSeek key只从服务器旧项目私有`.env`读取，交付包不包含密钥。

## 本地复核结果

优先阅读 `results/v2_report_zh.md`。`results/per_question_scores.csv`是700条独立验证/测试得分的简表，
`results/test/records.jsonl`是100题乘5方案的完整记录。
`cache/`保留调用输入与原始模型响应，`results/api_usage.jsonl`保留真实API用量。
`freeze.json`和各阶段`manifest.json`可核验源代码一致性。

`tools/report_v2.py`重新计算分数并核验父文档偏移、引用、逻辑组合和配对候选。
运行时传入解压后的包根目录，需Python及源码依赖（包括rank-bm25、numpy）：

```bash
python tools/report_v2.py /absolute/path/to/lightrag_v2_20261015
```

`file_hashes.json`用于校验每个交付文件，最终ZIP的SHA256在同级`delivery_manifest.json`。
不要将已查看的100题继续作为下一版算法的盲测集。

## 将算法迁入其他部署

`algorithm_v2.patch`以干净的b9009d237c3b432ea1139fccf1102fa6b9b4247e为基线，已通过`git apply --check`。
它不适用于任意已改动工作区；先检查差异，保留自己的修改。
`project/`含完整独立源码；`selected_source.tar.gz`是最终快照，trial1-3快照用于回溯失败尝试。
原有默认入口没有切换，需显式调用`make_corrective_chain`或`scripts/ask_corrective.py`。

```bash
pip install -e '.[real,local,test]'
PYTHONPATH=src python scripts/ask_corrective.py 'Your question' \
  --corpus /absolute/path/to/corpus.json \
  --reranker /absolute/path/to/bge-reranker-v2-m3 \
  --variant full
```

完整依赖版本见`requirements.freeze.txt`。复现此次分数应使用相同模型修订、语料、图索引与配置，
而不是只安装浮动版本。远端API以后可能变化，temperature=0也不保证再次调用逐字相同。
新建语料库须另行执行项目已有入库流程，并保持文档与父语料映射一致。

## 实验边界

`project/experiments/v2_experiment.py`是本服务器的可审计实验驱动，目录常量绑定此次部署；
迁移到其他服务器须调整路径，并作为新的实验保存，不能继续声称源码哈希与本次相同。
本次验证40题后冻结，再评估全新100题；未根据留出结果继续改算法。

本轮没有新增RAGBench分数。构造反例通过率、已作答题精度、开发集分数都不能替代100题全量EM。
程序保证来源编号/原文偏移和给定原子真值下的逻辑组合，不保证模型的原子事实判断必然正确。
每秒GPU采样不是显存分配器的精确峰值，不代表首次入库或历史全部运行的资源上限。

# 观微算法队参赛成果

河南大学 · 韩昌达、张中瑜、李嘉栋

## 阅读入口

| 成果 | 文件 |
| --- | --- |
| 完整参赛报告 | [PDF](report/观微证据链参赛报告.pdf)、[网页](report/观微证据链参赛报告.html) |
| 图表与机制图 | [矢量图及图片](report/图表/) |
| 三分钟项目视频 | [MP4](video/观微证据链三分钟项目介绍.mp4)，1920×1080，30 帧，180 秒 |
| 交互网页视频 | [离线 HTML](video/观微证据链三分钟介绍.html)，下载后直接打开 |
| 配音与字幕 | [旁白](video/项目介绍旁白.wav)、[字幕](video/项目介绍字幕.srt)、[分镜](video/分镜文稿.json) |
| 冻结实验结果 | [实验报告](experiments/20261015/results/v2_report_zh.md)、[逐题成绩](experiments/20261015/results/per_question_scores.csv) |
| 测试集原始记录 | [100 题、五方案](experiments/20261015/results/test/) |
| 验证与开发记录 | [验证集](experiments/20261015/results/validation/)、[开发迭代](experiments/20261015/results/dev/) |
| 视频验收 | [成片解码与播放](video/验收/成片验收.json)、[完整播放同步检查](video/验收/完整播放检查.json) |

## 源码与复核

最终优化源码位于仓库根目录 `src/evidencechain/`，入口为 `scripts/ask_corrective.py`；实验驱动位于 `experiments/`。真实模型调用需要自行配置私有 `.env`，仓库不包含密钥、模型权重或服务器密码。

先安装基础测试依赖并执行单元测试：

```bash
python -m pip install -e '.[test]' rank-bm25==0.2.2 numpy
python -m pytest -q
```

真实运行依赖与参数见 [算法说明](../docs/corrective_v2.md)。历史实验的语料索引、模型修订、数据划分与冻结协议记录于 [实验目录](experiments/20261015/)。公开数据和索引需按原实验配置另行准备，仓库不重复上传新闻语料与模型权重。

报告和视频制作脚本分别存放于 `report/source/`、`video/source/`。这些脚本保留制作时的本地路径，重新制作前需调整路径与浏览器配置；现成 HTML、PDF 和 MP4 无需制作环境即可使用。视频配音为中文合成男声，字幕已烧录到 MP4。

`manifest.json` 记录成果文件大小与 SHA256。开发失败尝试、验证器拒答和错误样例一并保留；本次 86% 为冻结留出集完全匹配率，不是全部公开基准的通用分数。

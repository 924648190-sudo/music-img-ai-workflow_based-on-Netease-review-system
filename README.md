# 让音乐成为生图prompt中的一个环节——基于网易云音乐的ai风格生图prompt生成器 v3.1ENV

这是一个用于 Dify 的音乐视觉化工作流：将歌曲、关联影视文化、封面/MV 图像资料和有效听众评论转译为图像生成的视觉风格描述，旨在为创作者提供更自由的描述空间和辅助描述工具。
本项目基于网易云音乐对于音乐的背景资料、MV信息以及公众评论区的内容进行风格关键词的抓取。
*prompt生成以用户明确提出的画面要求优先。
*当前输出结果仅为prompt，未接入生图环节

## workflow

用户输入：带有网易云歌曲分享url的描述
workflow：明确指向歌曲➔网易云背景信息收集与分析➔现有视觉参考（MV/专辑封面）➔评论区筛选以及氛围提炼➔综合信息收束与视觉化风格改写➔结合用户input进行场景化改写➔输出最终结果
*下一个版本发布时会对workflow进行视觉化的制作

## curent version

--v3.1 ENV
1. 对于通用环境、大众歌曲，已经能够生成比较符合歌曲氛围的（测试样本20条，综合评分高于80/100）
2. 目前的生成大部分内容都基于歌曲链接所能够获得的相关信息进行风格关键词的提炼，部分过于小众或者风格化不太明显的歌曲可能在氛围生成方面的能力不是很强；
3. 生成的提示词结果暂未优化，预计在下一个版本中对返回结果进行系统性的整理和优化；
4. 结果生成会参考评论区中公众对于音乐的评价，尽管对于评论增加了一轮筛选（总共20条有效评论，最多审阅100条），但无法评估评论区内容是否对结果生成起到正面作用；

## next version
1. 更完善的项目描述
2. workflow中的process整合与改写，精简架构，加速生成
3. 输出结果的效果精进，会更精简，让结果能够嵌入其他工作流

## 使用方法

1. 在自己的 Dify 工作区导入 `music-visual-style-3.1.yml`。
2. 配置自己的模型供应商凭据或可用额度，确认各节点选用的模型可调用。节点 134、176 需要支持图像输入的模型；其余 LLM 节点需要文本分析和结构化输出能力。若当前模型名不可用，改选自己的兼容模型。
3. 填写必填字符串 `userinput_query`，可以混合画面描述、歌曲分享链接及其他作品参考；`song_url` 为选填字符串，你可以指向性的填入歌曲分享链接。
4. 在 Dify 中运行，获取最终视觉风格提示词。没有具体画面要求时只描述风格，不自动添加人物与故事。

*在10.31日以前，你也可以直接访问Dify Web App进行测试，https://udify.app/workflow/orNgMGFGmi3l2sVx
本仓库不包含维护者 API Key。导入到自己的工作区后，调用使用自己配置的模型凭据或额度，不会因复制工作流而获得维护者的调用资格。



## 核心文件

| 文件 | 用途 |
|---|---|
| `music-visual-style-3.1.yml` | 可直接导入 Dify 的完整工作流 |
| `workflow-3.1.json` | 与 YAML 对应的结构化工作流定义 |
| `code/` | 代码节点与共用实现 |
| `prompts/` | 输入理解、评论筛选、风格规划与审查提示词 |
| `build_31.py`、`comment_patch.py` | 工作流构建及评论筛选编排 |
| `baseline-online-3.0.json` | 构建依赖的历史结构基线 |
| `source-directory.json` | 公开艺人资料地址索引 |

如需重新构建，安装 Python 3.10+ 和 Ruby（标准库 JSON/YAML），在仓库根目录运行：

```bash
python3 -B build_31.py
```

*直接导入现成 YAML 无需运行构建脚本。

## 配置api

导入 `music-visual-style-3.1-env.yml` 创建独立的 **3.1 ENV** 应用。在 Dify 顶部「环境变量」中配置：

| 变量 | 类型 | 设置 |
|---|---|---|
| `MODEL_API_KEY` | Secret | 在各部署环境自行填写；仓库中留空 |
| `MODEL_API_BASE_URL` | String | 默认 `https://api.deepseek.com`，可改为兼容接口的 HTTPS 基础地址 |
| `MODEL_TEXT_NAME` | String | 默认 `deepseek-flash`，需支持 JSON 对象输出 |
| `MODEL_VISION_NAME` | String | 默认 `deepseek-flash`，需同时支持图片输入与 JSON 对象输出 |

ENV 版本通过 HTTP 请求头直接引用 Secret，包含 98 个节点、125 条连接，不使用工作区模型凭据回退。未配置密钥时先返回配置提示，不发起请求。接口必须兼容 OpenAI Chat Completions 的 `messages`、`image_url` 与 `response_format`。

分发的是变量定义，每个环境单独配置密钥。不要把实际密钥提交 Git；从 Dify 导出时不要勾选包含 Secret，并在上传前确认 `MODEL_API_KEY.value` 为空。Dify 允许显式导出 Secret，不能仅依赖变量类型防止泄露。

`env_adapter.py` 与 `build_env.py` 为 ENV 核心源码，`workflow-3.1-env.json` 为结构化定义。重新构建：`python3 -B build_env.py`。HTTP 版本在结果解析节点的 `usage` 输出中保留用量；Dify 原生 LLM Token 面板不再自动汇总这些请求。原版 3.1 文件和分析提示词保持独立。

## 范围与限制
仓库仅分发工作流核心源码，不包含测试、环境模板、运行日志、截图、历史归档或第三方研究附件。

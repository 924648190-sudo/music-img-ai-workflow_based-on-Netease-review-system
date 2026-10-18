# 音乐与影视参考 → 视觉风格提示词 · 3.1

用于 Dify 的音乐视觉化工作流：将歌曲、关联影视文化、封面/MV 图像资料和有效听众评论转译为图像生成的视觉风格描述。用户明确提出的画面要求优先。

## 使用

1. 在自己的 Dify 工作区导入 `music-visual-style-3.1.yml`。
2. 配置自己的模型供应商凭据或可用额度，确认各节点选用的模型可调用。节点 134、176 需要支持图像输入的模型；其余 LLM 节点需要文本分析和结构化输出能力。若当前模型名不可用，改选自己的兼容模型。
3. 填写必填字符串 `userinput_query`，可混合画面描述、歌曲分享链接及其他作品参考；`song_url` 为选填字符串。
4. 在 Dify 中运行，获取最终视觉风格提示词。没有具体画面要求时只描述风格，不自动添加人物与故事。

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

直接导入现成 YAML 无需运行构建脚本。

## 使用工作流 Secret 的 ENV 版本

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

当前工作流包含 77 个节点、104 条连接；最多保留 20 条有效评论，按需有界补采，不足时记录缺口。资料检索不等于实际音频听辨；外部接口、模型及插件可用性取决于使用者环境。两个 RAG 当前未接入。

仓库仅分发工作流核心源码，不包含测试、环境模板、运行日志、截图、历史归档或第三方研究附件。

## 许可证

采用仓库根目录 `LICENSE` 所载 MIT License。第三方作品、歌词、评论和外部参考资料的权利归原权利人所有。

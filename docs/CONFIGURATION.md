# 配置与密钥边界

## Dify 中运行工作流

导入 `music-visual-style-3.1.yml`，检查模型供应商、模型名和视觉能力是否在你的工作区可用，再运行。公开检索接口当前不需要 API Key。

本项目的 LLM 节点使用 Dify 的模型供应商插件。**这些节点不读取本机 `.env`，也不会因为定义了 `DEEPSEEK_API_KEY` 就自动完成鉴权。** 模型供应商凭据需要在你自己的 Dify 工作区「模型供应商」中配置，由 Dify 管理；源码和 DSL 只保留供应商与模型选择，不携带供应商密钥。自托管 Dify 的环境变量也不等于工作流环境变量。

若以后添加需要 API Key 的 HTTP 节点，在 Dify 工作流中创建 Secret 类型环境变量，例如 `EXTERNAL_API_KEY`，在节点请求头中引用 `Bearer {{#env.EXTERNAL_API_KEY#}}`。导出前确认密钥值为空，不要把真实值写进代码、提示词、节点默认值或普通字符串环境变量。本版本没有需要这种鉴权的 HTTP 节点，因此没有增加无效的密钥占位节点。

## 从环境变量调用已发布应用

`scripts/run_workflow.py` 使用以下环境变量：

| 变量 | 用途 |
|---|---|
| `DIFY_API_KEY` | 已发布 Dify 应用的 API Key；必填，只在运行时读取 |
| `DIFY_API_BASE_URL` | API 基础地址；默认 `https://api.dify.ai/v1`，要求 HTTPS |
| `DIFY_API_TIMEOUT` | 等待秒数，默认 360 |

可由进程环境、CI Secret 或本地 `.env` 提供。已有进程环境优先于 `.env`。本地文件仅支持普通 `KEY=value`，不执行 shell、不展开 `${...}`。

```bash
cp .env.example .env
# 在本地编辑器中填写 .env 的 DIFY_API_KEY。
python3 scripts/run_workflow.py --input-file examples/input.json
```

必须先在自己的 Dify 中发布该应用并创建应用 API Key；导入草稿本身不能通过应用 API 调用。输入和结果会交给你配置的 Dify 与模型供应商处理。该脚本仅输出工作流最终输出，不保存原始请求/响应，不打印密钥、响应头或错误正文。

模型供应商 API Key 与 Dify 应用 API Key 是两种不同凭据，不能互换。发布源码没有包含任何真实密钥，也没有为你生成或迁移线上凭据。

参考：[Dify API 文档](https://docs.dify.ai/en/api-reference/guides/get-started)、[Dify 工作流模型及环境变量实现](https://github.com/langgenius/dify/blob/main/api/models/workflow.py)。

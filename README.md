# 音乐与影视参考 → 视觉风格提示词 · 3.1

将歌曲、关联影视文化、可获得的封面/MV 图像资料和听众评论转译为图像生成的视觉风格描述。音乐作为参考之一，用户明确提出的画面要求优先。

## 导入 Dify

1. 导入 `music-visual-style-3.1.yml`。
2. 在自己的 Dify 工作区配置可用的模型供应商凭据，检查各 LLM 节点的模型与视觉能力。
3. 填写 `userinput_query`；可在其中混合画面描述、歌曲分享链接和其他作品参考。`song_url` 为可选字符串。
4. 在 Dify 预览中测试。需要通过 API 调用时，再发布应用并配置环境变量，见 [配置说明](docs/CONFIGURATION.md)。

Fork 用户应导入到**自己的 Dify 工作区**，配置自己的模型凭据或额度。源码不包含维护者的应用 API Key、模型凭据或应用调用地址绑定；复制代码不会获得维护者的模型使用额度。模型选择与所需视觉能力见 [模型依赖](docs/MODEL_REQUIREMENTS.md)。

## 文件

- `music-visual-style-3.1.yml`：发布用 Dify DSL。
- `workflow-3.1.json`：与 DSL 相同的结构化构建结果。
- `code/`、`prompts/`：代码节点、公共函数和提示词。
- `build_31.py`、`comment_patch.py`：从公开基线重建 3.1。
- `baseline-online-3.0.json`：构建所需的历史结构基线，已检查敏感配置。
- `test_31.py`：工作流结构、输入、评论筛选和输出约束的离线回归检查。
- `scripts/run_workflow.py`：通过环境变量鉴权的后端调用示例。
- `scripts/audit_release.py`：发布隐私检查；仅报告文件、行号和规则，不打印命中内容。

## 验证

Python 3.10+；构建另需 Ruby 标准库 JSON/YAML；可选的 YAML/JSON 兼容性检查需要 Node.js 和 `npm install`。

```bash
python3 -B test_31.py
python3 -B -m unittest discover -s tests -v
python3 scripts/audit_release.py
python3 -B scripts/simulate_fork.py
```

重建：`python3 -B build_31.py`。构建后再次执行上述检查。原始证据日志、用户标识、浏览器截图、历史归档与第三方研究附件均不在此发布目录内。测试中的分享短链为虚构值，不应发起网络请求。

## 当前限制

工作流以资料和图像参考为主，没有进行实际音频听辨。评论最多保留 20 条有效样本，不足时报告缺口；有界补采不会保证始终获取到 20 条。外部接口可能失败、限流或改变；模型供应商与视觉模型需自行验证可用性。两个 RAG 未接入，极简画面专项调整暂缓。

本次 GitHub 发布准备完成的是本地脱敏与离线检查，没有进行真实凭据调用或重新完成云端测试。

已完成本地 Git 提交/克隆模拟：克隆中不含模拟的本地密钥，工作流可原样重建；无密钥时不发起请求，配置使用者模拟密钥时只使用该凭据。详见 [代码审查与 fork 验证报告](docs/CODE_REVIEW.md)。

## 发布范围

仅将本目录作为 Git 仓库根目录。上级目录含私人存档和整理清单，不应上传。原始第三方图片、歌词、评论记录及研究表格不作为本项目的许可内容分发。目标 GitHub 仓库已采用 MIT License，以仓库根目录的 `LICENSE` 为准。

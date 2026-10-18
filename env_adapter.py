"""Build OpenAI-compatible model requests without reading or exposing API keys."""

import ipaddress
import json
import re
from urllib.parse import urlsplit


def endpoint(base_url):
    base = str(base_url or "").strip().rstrip("/")
    parsed = urlsplit(base)
    host = (parsed.hostname or "").lower()
    valid = (parsed.scheme == "https" and host and not parsed.username
             and not parsed.password and not parsed.query and not parsed.fragment)
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        valid = False
    try:
        if not ipaddress.ip_address(host).is_global:
            valid = False
    except ValueError:
        pass
    if not valid:
        raise ValueError("MODEL_API_BASE_URL 必须是公开 HTTPS 模型服务地址，不含账号、查询参数或片段。")
    return base if parsed.path.rstrip("/").endswith("/chat/completions") else base + "/chat/completions"


def request_payload(templates, values, model, base_url, image_url=""):
    model = str(model or "").strip()
    if not model or len(model) > 200 or any(ord(c) < 32 for c in model):
        raise ValueError("请配置有效的文本或视觉模型名称。")

    def substitute(match):
        selector = match.group(1)
        if selector not in values:
            raise ValueError("模型请求缺少上游输入变量。")
        value = values[selector]
        return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)

    messages = [{"role": part["role"], "content": re.sub(
        r"\{\{#([^#]+)#\}\}", substitute, part["text"])} for part in templates]
    if image_url:
        parsed = urlsplit(image_url)
        host = (parsed.hostname or "").lower()
        if (parsed.scheme != "https" or parsed.username or parsed.password
                or not any(host == domain or host.endswith("." + domain)
                           for domain in ("music.126.net", "music.163.com"))):
            raise ValueError("视觉参考仅接受已核验的公开音乐平台封面地址。")
        users = [message for message in messages if message["role"] == "user"]
        if not users:
            raise ValueError("视觉请求缺少用户消息。")
        users[-1]["content"] = [
            {"type": "text", "text": users[-1]["content"]},
            {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}},
        ]
    body = {"model": model, "messages": messages, "stream": False,
            "response_format": {"type": "json_object"}}
    return {"body": json.dumps(body, ensure_ascii=False), "endpoint": endpoint(base_url)}


def completion_result(body, status_code, fallback=None):
    # Remote errors may echo input or credentials. Never include their body in errors.
    result = None
    try:
        data = json.loads(body)
        choices = data.get("choices", [])
        if int(status_code) == 200 and choices and isinstance(choices[0], dict):
            choice = choices[0]
            content = choice.get("message", {}).get("content")
            if choice.get("finish_reason") == "stop" and isinstance(content, str) and content.strip():
                # All original model prompts request a JSON object.
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    usage = data.get("usage", {})
                    allowed = ("prompt_tokens", "completion_tokens", "total_tokens",
                               "prompt_cache_hit_tokens", "prompt_cache_miss_tokens")
                    usage = {k: v for k, v in usage.items()
                             if k in allowed and isinstance(v, int) and not isinstance(v, bool) and v >= 0}
                    result = {"text": content, "usage": json.dumps(usage), "api_status": "ok"}
    except (ValueError, TypeError, AttributeError, OverflowError):
        pass
    if result is not None:
        return result
    if fallback is not None:
        return {"text": fallback, "usage": "{}", "api_status": "unavailable"}
    raise ValueError("模型 API 调用未成功或未返回完整 JSON，请检查环境变量、模型支持及私有运行记录。")

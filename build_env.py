"""Generate a separate Dify 3.1 ENV workflow; distribute an empty Secret value."""

import copy
import json
import re
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# JSON-mode providers occasionally omit a final closing brace even with finish_reason=stop.
# This bounded repair only closes containers; it never invents field values or retries a paid call.
REVIEW_REPAIR_SOURCE = '''
def repair_review_response(body, status_code):
    try:
        data = json.loads(body)
        choice = data["choices"][0]
        if int(status_code) != 200 or choice.get("finish_reason") != "stop":
            return body, False
        content = choice["message"]["content"]
        try:
            json.loads(content)
            return body, False
        except ValueError:
            pass
        stack, quoted, escaped = [], False, False
        for char in content:
            if quoted:
                if escaped:
                    escaped = False
                elif char == chr(92):
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char in "{[":
                stack.append(char)
            elif char in "}]":
                if not stack or stack.pop() != {"}": "{", "]": "["}[char]:
                    return body, False
        if quoted or not 0 < len(stack) <= 4:
            return body, False
        suffix = "".join({"{": "}", "[": "]"}[char] for char in reversed(stack))
        repaired = content + suffix
        if not isinstance(json.loads(repaired), dict):
            return body, False
        choice["message"]["content"] = repaired
        return json.dumps(data, ensure_ascii=False), True
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return body, False
'''


def build():
    workflow = json.loads((ROOT / "workflow-3.1.json").read_text())
    graph = workflow["workflow"]["graph"]
    nodes, edges = graph["nodes"], graph["edges"]
    original_nodes = copy.deepcopy(nodes)
    original = {n["id"]: n for n in original_nodes}
    registry = {n["id"]: n for n in nodes}
    adapter = (ROOT / "env_adapter.py").read_text()
    # Every other native code node and prompt is unchanged in this variant.
    for node in nodes:
        for key in ("position", "positionAbsolute"):
            node[key]["x"] *= 3
        node["selected"] = False
        node["data"]["selected"] = False

    def variable(name, selector, kind="string"):
        return {"variable": name, "value_selector": selector, "value_type": kind}

    def output(kind="string"):
        return {"type": kind, "children": None}

    def code_data(title, source, variables, outputs):
        compile(source, title, "exec")
        return {"title": title, "type": "code", "desc": "不读取密钥；密钥仅由模型 HTTP 节点引用。",
                "code_language": "python3", "code": source, "variables": variables,
                "outputs": {name: output(kind) for name, kind in outputs.items()}, "selected": False}

    def append(identifier, data, x, y):
        node = {"id": identifier, "type": "custom", "data": data,
                "position": {"x": x, "y": y}, "positionAbsolute": {"x": x, "y": y},
                "width": 260, "height": 120, "sourcePosition": "right", "targetPosition": "left",
                "selected": False}
        nodes.append(node)
        registry[identifier] = node
        return node

    def connect(source, target, handle="source"):
        edges.append({"id": source + "-" + handle + "-" + target, "source": source,
                      "target": target, "sourceHandle": handle, "targetHandle": "target",
                      "type": "custom", "data": {"sourceType": registry[source]["data"]["type"],
                      "targetType": registry[target]["data"]["type"],
                      "isInIteration": False, "isInLoop": False}})

    vision_sources = {"134": ("133", ["131", "cover_url"]),
                      "176": ("175", ["173", "cover_url"])}
    model_ids = []
    for prior in original_nodes:
        if prior["data"]["type"] != "llm":
            continue
        identifier, data = prior["id"], prior["data"]
        model_ids.append(identifier)
        is_vision = identifier in vision_sources
        request_id = vision_sources[identifier][0] if is_vision else "3" + identifier
        http_id = "4" + identifier
        position = registry[identifier]["position"]
        templates = [{"role": part["role"], "text": part["text"]}
                     for part in data["prompt_template"]]
        selectors = list(dict.fromkeys(match for part in templates
                         for match in re.findall(r"\{\{#([^#]+)#\}\}", part["text"])))
        assert not any("API_KEY" in s for s in selectors)
        variables = [variable("model", ["env", "MODEL_VISION_NAME" if is_vision else "MODEL_TEXT_NAME"]),
                     variable("base_url", ["env", "MODEL_API_BASE_URL"])]
        variables.extend(variable("v" + str(i), selector.split("."))
                         for i, selector in enumerate(selectors))
        signature = "model: str, base_url: str" + "".join(
            ", v" + str(i) + ": str" for i in range(len(selectors)))
        mapping = "{" + ",".join(repr(selector) + ":v" + str(i)
                                  for i, selector in enumerate(selectors)) + "}"
        if is_vision:
            variables.append(variable("image_url", vision_sources[identifier][1]))
            signature += ", image_url: str"
        request_source = adapter + "\n\nTEMPLATES = " + repr(templates) + "\n\ndef main(" + signature + ") -> dict:\n"
        request_source += "    return request_payload(TEMPLATES," + mapping + ",model,base_url"
        request_source += ",image_url)\n" if is_vision else ")\n"
        request_data = code_data(data["title"] + " · 请求体", request_source, variables,
                                 {"body": "string", "endpoint": "string"})
        if is_vision:
            # Reuse the image-download step: the model now fetches the verified public URL.
            registry[request_id]["data"] = request_data
        else:
            append(request_id, request_data, position["x"] - 640, position["y"])
            for edge in edges:
                if edge["target"] == identifier:
                    edge["target"] = request_id
        http_data = copy.deepcopy(original["120"]["data"])
        http_data.update({
            "title": data["title"] + " · 模型 API", "method": "post",
            "desc": "仅从 Secret 环境变量鉴权；无供应商凭据回退，不自动重试付费请求。",
            "url": "{{#" + request_id + ".endpoint#}}",
            "authorization": {"type": "api-key", "config": {
                "type": "bearer", "api_key": "{{#env.MODEL_API_KEY#}}", "header": ""}},
            "headers": "Content-Type:application/json\nAccept:application/json",
            "body": {"type": "raw-text", "data": [{"key": "", "type": "text",
                         "value": "{{#" + request_id + ".body#}}", "file": []}]},
            "timeout": {"connect": 10, "read": 300, "write": 30,
                        "max_connect_timeout": 10, "max_read_timeout": 300, "max_write_timeout": 30},
            "retry_config": {"retry_enabled": False, "max_retries": 0, "retry_interval": 1000},
            "ssl_verify": True,
        })
        append(http_id, http_data, position["x"] - 320, position["y"])
        fallback = next((item["value"] for item in data.get("default_value", [])
                         if item["key"] == "text"), None)
        parse_source = adapter + "\n\ndef main(body: str, status_code: int) -> dict:\n"
        parse_source += "    return completion_result(body,status_code," + repr(fallback) + ")\n"
        if identifier == "215":
            parse_source = adapter + REVIEW_REPAIR_SOURCE + "\n\ndef main(body: str, status_code: int) -> dict:\n"
            parse_source += "    body, repaired = repair_review_response(body,status_code)\n"
            parse_source += "    result = completion_result(body,status_code)\n"
            parse_source += "    if repaired: result['api_status'] = 'ok_repaired_json'\n    return result\n"
        registry[identifier]["data"] = code_data(
            data["title"] + " · 结果解析", parse_source,
            [variable("body", [http_id, "body"]), variable("status_code", [http_id, "status_code"], "number")],
            {"text": "string", "usage": "string", "api_status": "string"})
        if is_vision:
            edges[:] = [edge for edge in edges if not (
                edge["source"] == request_id and edge["target"] == identifier)]
        connect(request_id, http_id)
        connect(http_id, identifier)

    # No API request, paid or public, occurs when the local deployment key is absent.
    start = registry["100"]["position"]
    guard_id, message_id, end_id = "3001", "3002", "3003"
    append(guard_id, {"title": "本环境已配置模型 Secret？", "type": "if-else", "selected": False,
           "desc": "缺少本环境密钥时立即结束，不回退到维护者或工作区供应商凭据。",
           "cases": [{"case_id": "true", "logical_operator": "and", "conditions": [{
               "id": "model-key-present", "varType": "string", "variable_selector": ["env", "MODEL_API_KEY"],
               "comparison_operator": "not empty", "value": ""}]}]}, start["x"] + 300, start["y"])
    message_source = 'def main() -> dict:\n    return {"message":"请在环境变量中填写本部署的 MODEL_API_KEY（Secret），并确认接口地址及模型名称。"}\n'
    append(message_id, code_data("缺少密钥 · 配置提示", message_source, [], {"message": "string"}),
           start["x"] + 620, start["y"] + 500)
    append(end_id, {"title": "仅返回配置提示", "type": "end", "selected": False,
           "outputs": [{"variable": "configuration_required", "value_selector": [message_id, "message"]}]},
           start["x"] + 940, start["y"] + 500)
    for edge in edges:
        if edge["source"] == "100":
            edge["source"] = guard_id
            edge["sourceHandle"] = "true"
    connect("100", guard_id)
    connect(guard_id, message_id, "false")
    connect(message_id, end_id)
    # Update edge metadata after node type replacements and ensure stable unique IDs.
    for index, edge in enumerate(edges):
        edge["id"] = "env-edge-" + str(index)
        edge["data"]["sourceType"] = registry[edge["source"]]["data"]["type"]
        edge["data"]["targetType"] = registry[edge["target"]]["data"]["type"]

    env_specs = [
        ("MODEL_API_KEY", "secret", "", "本部署的模型 API Key；分发时必须留空。"),
        ("MODEL_API_BASE_URL", "string", "https://api.deepseek.com", "HTTPS OpenAI-compatible 基础地址，可包含 /v1。"),
        ("MODEL_TEXT_NAME", "string", "deepseek-flash", "文本分析模型名称。"),
        ("MODEL_VISION_NAME", "string", "deepseek-flash", "支持图片输入的模型名称。"),
    ]
    workflow["workflow"]["environment_variables"] = [
        {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, "music-visual-workflow/3.1-env/" + name)),
         "name": name, "value_type": kind, "value": value, "description": description,
         "selector": ["env", name]} for name, kind, value, description in env_specs]
    workflow["dependencies"] = []
    workflow["app"]["name"] = "音乐 × 影视 → 视觉风格 3.1 ENV"
    workflow["app"]["description"] = "3.1 ENV：模型 HTTP 调用直接读取工作流 Secret；分发不含密钥，不使用工作区供应商凭据回退。原分析与输出逻辑保留；RAG未接入。"
    graph["viewport"] = {"x": 0, "y": 0, "zoom": 0.15}
    assert not any(n["data"]["type"] == "llm" for n in nodes)
    assert all(e["value"] == "" for e in workflow["workflow"]["environment_variables"] if e["value_type"] == "secret")
    return workflow


if __name__ == "__main__":
    result = build()
    raw = json.dumps(result, ensure_ascii=False, indent=2)
    (ROOT / "workflow-3.1-env.json").write_text(raw + "\n")
    (ROOT / "music-visual-style-3.1-env.yml").write_bytes(subprocess.check_output(
        ["ruby", "-rjson", "-ryaml", "-e", "puts YAML.dump(JSON.parse(STDIN.read))"], input=raw.encode()))
    graph = result["workflow"]["graph"]
    print(json.dumps({"nodes": len(graph["nodes"]), "edges": len(graph["edges"]),
                      "secret_value_in_export": False, "native_llm_nodes": 0}))

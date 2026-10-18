def main(meta:str)->dict:
    import json
    return {"result":json.dumps({"scope":"image_unavailable","metadata":meta,"visual_facts":{},"uncertainties":["平台未返回可用专辑封面"]},ensure_ascii=False)}
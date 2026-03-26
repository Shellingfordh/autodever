"""
审查模块：把 instruction + files 告知 AI，并请求 PASS/FAIL 与审查意见（可用于下一轮改进）
返回 (pass_flag: bool, note: str)
"""
from ai_client import call_ai_text
import json

async def review_code(instruction: str, files: dict):
    # 为避免发送太大内容，可只发送关键文件或长度裁剪。这里为简单实现直接发送。
    files_preview = {k: (v if len(v) < 4000 else v[:4000] + "\n...TRUNCATED...") for k, v in files.items()}
    prompt = f"""
你是资深工程师审查员。任务需求:
{instruction}

所给文件列表（key: filename, value: content）:
{json.dumps(files_preview, indent=2, ensure_ascii=False)}

请根据以下规则给出审查结果：
- 如果这些文件能实现需求并且能直接运行，返回 JSON: {{"result": "PASS", "note":"简要说明"}}
- 否则返回 JSON: {{"result": "FAIL", "note":"指出需要修改的问题，越具体越好"}}
返回内容必须是严格的 JSON（不要额外说明）。
"""
    resp = await call_ai_text(prompt)
    # 尝试解析 JSON
    try:
        # 找出 JSON 块
        start = resp.index("{")
        end = resp.rindex("}") + 1
        j = json.loads(resp[start:end])
        result = j.get("result", "").upper()
        note = j.get("note", "")
        return (result == "PASS"), note
    except Exception:
        # 若解析失败，视为未通过并返回模型原文
        return False, f"审查解析失败，AI 原文: {resp}"

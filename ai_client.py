"""
与 OpenAI 的最小交互层，包含 call_ai_text（返回文本）与 call_ai_json（期望 JSON）
注意：该实现做了基础重试与简单异常处理。根据你的 API Key 和模型偏好修改 model 字段。
"""
import os
import httpx
import json
import time

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # 可按需替换

if not OPENAI_API_KEY:
    raise RuntimeError("需要环境变量 OPENAI_API_KEY")

HEADERS = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json"
}

async def call_ai_text(prompt: str, max_tokens=1500):
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.2
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{OPENAI_API_BASE}/chat/completions", headers=HEADERS, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

async def call_ai_json(prompt: str, max_tokens=2000, retries=2):
    # 我们要求模型输出严格 JSON，做一些简单的重试+解析容错
    for attempt in range(retries + 1):
        text = await call_ai_text(prompt, max_tokens=max_tokens)
        # 尝试提取 JSON 部分（如果模型前后有说明性文字）
        text_stripped = text.strip()
        # 找出首个 { 到最后的 } 区间
        try:
            start = text_stripped.index("{")
            end = text_stripped.rindex("}") + 1
            candidate = text_stripped[start:end]
            parsed = json.loads(candidate)
            return parsed
        except Exception:
            # 若解析失败，给模型更多约束再试一轮
            prompt = "请严格以 JSON 格式输出（不带解释文字），并确保 JSON 可用。上一次返回无法解析为 JSON，请只返回 JSON。需求如下：\n\n" + prompt
            await sleep_backoff(attempt)
            continue
    # 最后直接 raise
    raise ValueError("AI 未能返回有效 JSON")

async def sleep_backoff(n):
    await asyncio.sleep(min(2 ** n, 10))

"""
主服务：接收 /task 请求，驱动 AI 生成 -> 自审 -> 推送 -> 等待部署 成功返回 "hello world"
"""
import os
import asyncio
import json
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from ai_client import call_ai_json, call_ai_text
from reviewer import review_code
from github_push import push_files_to_github
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GITHUB_OWNER = os.getenv("GITHUB_OWNER")
GITHUB_REPO = os.getenv("GITHUB_REPO")
DEPLOY_URL = os.getenv("DEPLOY_URL")  # 最终检查的 URL（比如 Vercel 提供的 URL）
MAX_ROUNDS = int(os.getenv("MAX_ROUNDS", "5"))
WAIT_TIMEOUT = int(os.getenv("WAIT_TIMEOUT", "300"))  # seconds

if not OPENAI_API_KEY or not GITHUB_OWNER or not GITHUB_REPO:
    print("警告: 请确保环境变量 OPENAI_API_KEY, GITHUB_OWNER, GITHUB_REPO 已配置。")

class TaskRequest(BaseModel):
    instruction: str
    repo_branch: str = "main"
    commit_message: str = "AI 自动提交"

@app.post("/task")
async def handle_task(req: TaskRequest):
    instruction = req.instruction.strip()
    if not instruction:
        raise HTTPException(status_code=400, detail="instruction 不能为空")

    # 主循环：多轮生成 -> 自审 -> 推送 -> 等待部署
    for attempt in range(1, MAX_ROUNDS + 1):
        # 1) 让 AI 生成工程文件（JSON 格式 files: {filename: content}）
        gen_prompt = f"""
你是资深工程师：请根据用户需求生成一个可运行的 Python web 项目（FastAPI 或 Flask 均可）。
要求：
- 输出为一个严格的 JSON：{{ "files": {{ "<path>": "<content>", ... }} , "entrypoint": "<relative path to start file>" }}
- 每个文件内容为字符串（请确保正确转义）。
- 包含必要依赖文件 requirements.txt，Dockerfile（可选），README.md （简短启动步骤）。
用户需求:
{instruction}
"""
        try:
            gen_resp = await call_ai_json(gen_prompt)
        except Exception as e:
            return {"status": "error", "message": f"调用 AI 生成失败: {e}"}

        files = gen_resp.get("files") or {}
        entrypoint = gen_resp.get("entrypoint")

        if not files:
            # 如果格式解析失败，尝试用文本接口获取更多信息（容错）
            raw = await call_ai_text("生成失败，返回内容供调试：" + instruction)
            return {"status": "error", "message": "AI 返回无 files", "raw": raw}

        # 2) 自我审查
        try:
            pass_flag, review_note = await review_code(instruction, files)
        except Exception as e:
            pass_flag = False
            review_note = f"审查模块异常: {e}"

        if not pass_flag:
            # 把审查意见加入下一轮 prompt（让 AI 改进）
            improvement_prompt = f"""
上一次生成未通过审查，审查意见如下：
{review_note}

请基于上一次输出的文件进行改进（只返回 JSON 格式的 files），并修复审查中指出的问题。
"""
            try:
                # 简单地把审查意见交给 AI 生成改进版
                gen_resp = await call_ai_json(improvement_prompt)
                files = gen_resp.get("files") or files  # 若失败则保留旧文件发起下一轮
            except Exception:
                # 继续下一轮
                pass
            # 进入下一轮
            continue

        # 3) 推送到 GitHub
        try:
            push_result = push_files_to_github(
                owner=os.getenv("GITHUB_OWNER"),
                repo=os.getenv("GITHUB_REPO"),
                files=files,
                branch=req.repo_branch,
                commit_message=req.commit_message
            )
        except Exception as e:
            return {"status": "error", "message": f"推送到 GitHub 失败: {e}"}

        # 4) 等待部署（轮询 DEPLOY_URL）
        if DEPLOY_URL:
            deployed = await wait_for_deploy(DEPLOY_URL, WAIT_TIMEOUT)
            if deployed:
                return {"status": "success", "final": "hello world", "attempts": attempt, "push": push_result}
            else:
                # 若没部署成功，继续下一轮（让 AI 修复）
                continue
        else:
            # 没配置 DEPLOY_URL 时，直接返回成功并附带推送信息
            return {"status": "success", "final": "hello world", "attempts": attempt, "push": push_result}

    return {"status": "failed", "message": f"在 {MAX_ROUNDS} 轮内未能达到通过或部署成功。最后一次审查备注: {review_note}"}


async def wait_for_deploy(url: str, timeout_s: int):
    import httpx, time
    start = time.time()
    interval = 5
    async with httpx.AsyncClient(timeout=10) as client:
        while time.time() - start < timeout_s:
            try:
                r = await client.get(url)
                text = r.text.lower()
                if r.status_code == 200 and "hello world" in text:
                    return True
            except Exception:
                pass
            await asyncio.sleep(interval)
    return False

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)

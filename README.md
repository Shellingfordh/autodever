# AI 自动写码并自审 -> 推送 -> 自动部署（MVP）

## 概览
这个项目是一个完整的原型：接收 `instruction`，调用 OpenAI 生成代码并自我审查，如果通过则自动推送到指定 GitHub 仓库并等待部署成功（检查 `DEPLOY_URL` 页面包含 `hello world`）。

## 运行前准备
在仓库中创建 `.env`，并设置以下环境变量：

OPENAI_API_KEY=sk-xxx
GITHUB_TOKEN=ghp_xxx
GITHUB_OWNER=你的GitHub用户名或组织
GITHUB_REPO=目标仓库名
DEPLOY_URL=https://your-deployed-url.vercel.app # 可选，用于检查是否部署完成
MAX_ROUNDS=5
WAIT_TIMEOUT=300



可选：
VERCEL_TOKEN=在 GitHub Secrets 中配置以便 GitHub Actions 使用 vercel CLI 部署



## 快速启动（本地测试）
1. 安装依赖：
```bash
pip install -r requirements.txt
启动服务：


uvicorn main:app --reload --port 8000
发起任务：


curl -X POST "http://localhost:8000/task" \
  -H "Content-Type: application/json" \
  -d '{"instruction": "写一个最简单的 Flask 应用，根路径显示 hello world"}'
注意与安全
GITHUB_TOKEN 需要有 push 权限。建议使用受限的机器账号 token。

该原型把 AI 生成的任意文件直接推送到仓库，请在受控仓库或测试仓库里先运行，避免恶意或低质量提交影响主仓库。

强烈建议把仓库设置为私有（或使用单独的测试 repo）。

拓展思路
把审查拆成多个 agent：代码生成 agent / 测试 agent / 安全审查 agent。

在推送前先在一个隔离的 Docker 环境里“本地运行并测试”再推送。

使用 GitHub PR 流程（创建分支 + PR），而不是直接 push 到 main。


## 使用建议与风险提示（必须读）
1. **先在测试仓库跑原型**：AI 会生成文件；为避免破坏现有主分支，请先把 `GITHUB_REPO` 指向**新建的测试仓库**。  
2. **权限控制**：为 `GITHUB_TOKEN` 使用权限受限的专用 token（只给 repo push 权限），不要用个人全权限 token。  
3. **审查策略**：当前审查完全由 AI 完成 —— 可行但不万无一失；建议在生产之前加入人审或自动化测试（static analysis、unit tests、sast）。  
4. **部署检测**：默认以页面包含 “hello world” 作为成功标准，你可以按需修改为更严格的 health-check（JSON 接口、状态码、端到端测试）。



## **1. 升级版目标**

> 让 AI 在最小人类干预的情况下，自主做项目、自主优化方法、自主调用 API。

### **核心能力**

* **任务规划**：根据目标自动拆解任务
* **自动调用 API**：调用 LLM、向量数据库、翻译、图像生成等
* **自我审查**：判断结果是否符合预期
* **自我学习**：根据反馈调整 prompt、策略、调用参数
* **可持续循环**：直到返回“hello world”或满足目标为止

---



2. 系统整体架构
scss
Copy code
┌─────────────────────────────┐
│   任务指令 (自然语言)        │
└────────────┬───────────────┘
             │
┌────────────▼────────────┐
│   控制器 (Controller)   │  ← 主循环
└───────┬─────┬──────────┘
        │     │
        │     │
┌───────▼─────▼──────────┐
│  执行器 (Executor)      │
│ - AI API 调用           │
│ - 数据采集              │
│ - 工具调用 (Google, Git)│
└─────────────┬──────────┘
              │
┌─────────────▼────────────┐
│   审查器 (Reviewer)      │
│ - 结果自检              │
│ - AI 多次复核           │
│ - 失败重试              │
└─────────────┬────────────┘
              │
┌─────────────▼────────────┐
│   自我学习器 (Trainer)   │
│ - 总结失败原因          │
│ - 自动优化 prompt       │
│ - 微调模型 (可选)      │
└─────────────┬────────────┘
              │
    ┌─────────▼────────┐
    │   持久存储 Memory │
    │  (向量数据库/日志)│
    └──────────────────┘
3. 技术选型

---



| 模块        | 技术/服务推荐                                | 用途            |
| --------- | -------------------------------------- | ------------- |
| **后端服务**  | FastAPI / Flask                        | 提供 AI 调用与循环管理 |
| **云端部署**  | GitHub Actions / Vercel / AWS Lambda   | 自动运行、随时触发     |
| **AI 模型** | OpenAI GPT-4.1 / Claude 3.5 / 自建 LLaMA | 执行任务、审查结果     |
| **记忆系统**  | Weaviate / Milvus / Pinecone           | 向量存储，长期学习     |
| **自我学习**  | RLHF + Prompt Tuning                   | 根据反馈优化策略      |
| **日志系统**  | Supabase / PostgreSQL                  | 存储循环日志与训练数据   |

---

## **4. 循环逻辑示例**

### **主循环伪代码**

```python
import time
import openai

TARGET_RESULT = "hello world"

def call_ai_api(prompt):
    # 调用 OpenAI
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    return response["choices"][0]["message"]["content"]

def reviewer(output):
    # 自我审查器
    review_prompt = f"""
    你是审查器，任务是判断以下输出是否符合要求：
    输出: {output}
    如果通过返回 "OK"，否则返回"FAIL"
    """
    result = call_ai_api(review_prompt)
    return result.strip().upper() == "OK"

def train_agent(failed_output):
    # 简单的自我学习逻辑
    # 提炼失败原因并更新提示词
    train_prompt = f"""
    我们的上一次尝试失败，输出是: {failed_output}
    请分析原因，并给出更优的策略。
    """
    new_strategy = call_ai_api(train_prompt)
    return new_strategy

def main_loop(initial_prompt):
    strategy = initial_prompt
    for i in range(100):  # 限制最大循环次数
        print(f"第 {i+1} 次执行中...")

        # 1. 执行任务
        output = call_ai_api(strategy)

        # 2. 审查结果
        if reviewer(output):
            print(f"任务完成 ✅: {output}")
            break
        else:
            # 3. 自我学习
            strategy = train_agent(output)
            print(f"策略更新为: {strategy}")
            time.sleep(1)

main_loop("请写一个Python函数返回hello world")
```

### **特点**

* 支持无限循环优化
* 失败 → 总结 → 策略更新 → 再尝试
* 可以接入外部工具（Google 搜索、API 抓取、GitHub 推送）

---

## **5. 自我学习升级**

### **第一阶段：Prompt 自学习（低成本）**

* 每次失败 → 自动生成新 prompt → 再次尝试
* 类似 **Chain-of-Thought** + **Self-Consistency**

### **第二阶段：强化学习 RLHF**

* 记录审查器的 OK/FAIL 反馈
* 形成 reward signal
* 基于 reward 更新策略
* 如果配合开源模型（如 LLaMA / Qwen），可以在本地持续微调

### **第三阶段：Agent + 多模型协作**

* 类似 **AutoGPT** / **BabyAGI**
* 一个 AI 负责执行
* 一个 AI 负责审查
* 一个 AI 负责优化策略
* 可以无限学习并自我进化

---




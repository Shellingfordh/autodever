"""
将文件推送到 GitHub 仓库（create or update files）
依赖 PyGithub
"""
import os
from github import Github
from github import InputGitTreeElement
import base64
import json

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise RuntimeError("需要环境变量 GITHUB_TOKEN")

def push_files_to_github(owner: str, repo: str, files: dict, branch: str = "main", commit_message: str = "AI 自动提交"):
    """
    files: dict of {path: content}
    """
    g = Github(GITHUB_TOKEN)
    full_repo = f"{owner}/{repo}"
    repository = g.get_repo(full_repo)

    # 获取最新提交的 tree
    ref = repository.get_git_ref(f"heads/{branch}")
    base_tree = repository.get_git_tree(ref.object.sha)
    element_list = []

    for path, content in files.items():
        # 确ure content is str
        if isinstance(content, dict) or isinstance(content, list):
            content = json.dumps(content, ensure_ascii=False, indent=2)
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        element = InputGitTreeElement(path, '100644', 'blob', content)
        element_list.append(element)

    new_tree = repository.create_git_tree(element_list, base_tree)
    parent = repository.get_git_commit(ref.object.sha)
    commit = repository.create_git_commit(commit_message, new_tree, [parent])
    ref.edit(commit.sha)

    return {"repo": full_repo, "branch": branch, "commit": commit.sha}

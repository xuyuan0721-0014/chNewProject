"""正文守门钩子：没加载 jianzhu-style、没读全细则和写作规矩，就不许改 正文/；
改过正文、没派 zhengwen-reviewer 审查，就不许收尾。

用法（在 .claude/settings.json 里挂）：
  record   PostToolUse(Read|Skill|Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell|Agent|Task)
           与 UserPromptSubmit：记下本会话读过什么、改过哪些正文、派没派审查
  reset    SessionStart(compact|clear)：上下文压缩或清空后清掉“读过”的账，须重读（待审的账保留）
  check    PreToolUse(Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell)：
           目标在 正文/ 下时查账，缺了就拒绝并列出缺哪几份，齐了放行并注入提醒
  stop     Stop：本会话改过正文、改完以后还没派 zhengwen-reviewer，就拦住收尾

账记在 .claude/hooks/state/<session_id>.json（已 gitignore）。
“读过”由钩子保证；“用对”由审查代理 .claude/agents/zhengwen-reviewer.md 出具清单，主会话据此修改。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.normpath(os.path.join(HERE, "..", ".."))
SKILL_DIR = os.path.join(PROJECT, ".claude", "skills", "jianzhu-style")
REF_DIR = os.path.join(SKILL_DIR, "references")
RULES = os.path.join(PROJECT, "写作规矩.md")
STATE_DIR = os.path.join(HERE, "state")

REMINDER = (
    "【写正文提醒】这次改动在 正文/ 下。"
    "必须使用项目技能 jianzhu-style（不是全局的 wuzei-style）：动笔前读完总纲与 references 下十二份细则，写作和复核时执行第零节；涉及的细则再回查。"
    "再照仓库根目录 写作规矩.md 第一节读完设定七份：章纲本章与前后各一章、卷纲本章所在小弧与信息差总表、上一章正文全文、"
    "交接文档第三节提到本章的条目、主线.md 第一节、地理.md 大野村格局、社会.md 第零节与总则；"
    "再按第4条按内容加读；章首注里写明读过哪几份（第5条）；"
    "伏笔对着章纲本章“伏笔/回收”一行走，写完逐条核，新冒出来的线记进章纲（第6条）；"
    "本章出场的每个人先在 02-人物/ 立好或补好小传、读完再写，写完逐个更新小传（第7条、第二节）。"
)

# Bash / PowerShell 命令里表示“写入、删除、移动”的迹象
WRITE_HINTS = re.compile(
    r"(open\([^)]*['\"][wa]\+?b?['\"]|\.write\(|write_text|sed\s+-i|\brm\b|\bmv\b|\bcp\b|\btee\b"
    r"|>|Set-Content|Add-Content|Out-File|Remove-Item|Move-Item|Copy-Item|Rename-Item|New-Item"
    r"|git\s+(rm|mv|checkout|restore|reset|stash))"
)
ZHENGWEN_PATH = re.compile(r"正文(?=[/\\\\\"'\s]|$)")
# 只算“不带 2>/dev/null 这类丢弃输出”的重定向
NULL_REDIRECT = re.compile(r"\d?>\s*(/dev/null|\$null|NUL)\b|2>&1")


def norm(path):
    return os.path.normcase(os.path.normpath(str(path))).replace("\\", "/")


def read_input():
    raw = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace").read()
    try:
        return json.loads(raw)
    except ValueError:
        return {}


def state_path(session_id):
    safe = re.sub(r"[^0-9A-Za-z_-]", "_", session_id or "unknown")
    return os.path.join(STATE_DIR, safe + ".json")


def load_state(session_id):
    try:
        with open(state_path(session_id), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"skill": False, "reads": []}


def save_state(session_id, state):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(state_path(session_id), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=0)


def required_files():
    refs = []
    if os.path.isdir(REF_DIR):
        refs = sorted(os.path.join(REF_DIR, n) for n in os.listdir(REF_DIR) if n.endswith(".md"))
    return refs + [RULES]


REVIEWER = "zhengwen-reviewer"


def record(data):
    sid = data.get("session_id")
    state = load_state(sid)
    state.setdefault("dirty", [])
    changed = False
    event = data.get("hook_event_name")
    if event == "UserPromptSubmit":
        prompt = str(data.get("prompt") or "")
        if re.match(r"\s*/jianzhu-style\b", prompt):
            state["skill"] = True
            changed = True
        if "跳过审查" in prompt and state["dirty"]:
            state["dirty"] = []  # 作者明说这次不审
            changed = True
    else:
        tool = data.get("tool_name")
        inp = data.get("tool_input") or {}
        if tool == "Skill" and str(inp.get("skill", "")).split(":")[-1] == "jianzhu-style":
            state["skill"] = True
            changed = True
        elif tool == "Read" and not inp.get("offset") and not inp.get("limit"):
            p = norm(inp.get("file_path", ""))
            if p == norm(os.path.join(SKILL_DIR, "SKILL.md")):
                state["skill"] = True
            if p not in state["reads"]:
                state["reads"].append(p)
            changed = True
        elif tool in ("Agent", "Task") and (
            str(inp.get("subagent_type", "")).split(":")[-1] == REVIEWER
            # 新建代理要到下个会话才注册；这时派通用代理并写明照审查说明办，也算
            or REVIEWER + ".md" in str(inp.get("prompt", ""))
        ):
            if state["dirty"]:
                state["dirty"] = []
                changed = True
        elif targets_zhengwen(data) and not only_deletes(data):
            label = zhengwen_label(data)
            if label not in state["dirty"]:
                state["dirty"].append(label)
                changed = True
    if changed:
        save_state(sid, state)


def only_deletes(data):
    """Bash/PowerShell 只是删除正文（rm、Remove-Item、git rm）时不算待审。"""
    if data.get("tool_name") not in ("Bash", "PowerShell"):
        return False
    cmd = NULL_REDIRECT.sub("", str((data.get("tool_input") or {}).get("command") or ""))
    rest = re.sub(r"(\brm\b|Remove-Item|git\s+rm)", "", cmd)
    return bool(re.search(r"(\brm\b|Remove-Item|git\s+rm)", cmd)) and not WRITE_HINTS.search(rest)


def zhengwen_label(data):
    inp = data.get("tool_input") or {}
    p = inp.get("file_path") or inp.get("notebook_path")
    if p:
        return os.path.relpath(os.path.normpath(p), PROJECT).replace("\\", "/")
    return "（" + data.get("tool_name", "命令") + " 改动了 正文/）"


def reset(data):
    """压缩或清空后清掉“读过”的账；待审的账留着，改过的正文照样要审。"""
    state = load_state(data.get("session_id"))
    dirty = state.get("dirty", [])
    try:
        os.remove(state_path(data.get("session_id")))
    except OSError:
        pass
    if dirty:
        save_state(data.get("session_id"), {"skill": False, "reads": [], "dirty": dirty})


def stop(data):
    if data.get("stop_hook_active"):
        return  # 这次收尾本身是被本钩子拦回来的，不再拦，免得死循环
    state = load_state(data.get("session_id"))
    dirty = state.get("dirty", [])
    if not dirty:
        return
    reason = (
        "【正文审查】本会话改过正文，改完以后还没有派审查代理 zhengwen-reviewer：\n- "
        + "\n- ".join(dirty)
        + "\n请用 Agent 工具派 zhengwen-reviewer（subagent_type 填 zhengwen-reviewer），在任务里写明待审的章节文件；"
        "本会话还没注册这个代理时，派 general-purpose，任务里写明“先读 .claude/agents/zhengwen-reviewer.md，照其中说明审查”。"
        "拿到清单后，“必须改”逐条改完，“建议改”酌情处理，再向作者汇报审查结论和改动。"
        "作者说“跳过审查”即可不审。"
    )
    sys.stdout.write(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=True))


def targets_zhengwen(data):
    tool = data.get("tool_name")
    inp = data.get("tool_input") or {}
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        p = norm(inp.get("file_path") or inp.get("notebook_path") or "")
        return "/正文/" in p or p.startswith("正文/")
    if tool in ("Bash", "PowerShell"):
        cmd = str(inp.get("command") or "")
        # 只认路径形式的“正文”（后接 / \ 引号 空白或结尾），“正文守门”这类说法不算
        if not ZHENGWEN_PATH.search(cmd):
            return False
        return bool(WRITE_HINTS.search(NULL_REDIRECT.sub("", cmd)))
    return False


def check(data):
    if not targets_zhengwen(data):
        return
    state = load_state(data.get("session_id"))
    read = set(state.get("reads", []))
    missing = []
    if not state.get("skill"):
        missing.append("jianzhu-style 技能（用 Skill 工具调用，或完整 Read 它的 SKILL.md）")
    for f in required_files():
        if norm(f) not in read:
            missing.append(os.path.relpath(f, PROJECT).replace("\\", "/"))
    if missing:
        reason = (
            "【正文守门】本会话（最近一次上下文压缩或清空之后）还没读全就要改 正文/，已拦下。"
            "先补齐下面这些，再重试这次改动：\n- " + "\n- ".join(missing) +
            "\n细则和写作规矩要用 Read 工具整份读（不带 offset/limit），用 Bash cat 读的不算。"
        )
        out = {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}
    else:
        out = {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": REMINDER,
        }}
    sys.stdout.write(json.dumps(out, ensure_ascii=True))


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    data = read_input()
    if not data:
        return
    {"record": record, "reset": reset, "check": check, "stop": stop}.get(mode, check)(data)


if __name__ == "__main__":
    main()

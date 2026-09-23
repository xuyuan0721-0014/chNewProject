"""PreToolUse 钩子：Write/Edit 目标在 正文/ 下时，提醒先加载 jianzhu-style、读完固定必读。只提醒，不拦截。"""
import io
import json
import sys

REMINDER = (
    "【写正文提醒】这次改动在 正文/ 下。"
    "先加载项目技能 jianzhu-style（不是全局的 wuzei-style）。"
    "动笔前照 SKILL.md 第零节第5条读完七份固定必读："
    "章纲本章与前后各一章、卷纲本章所在小弧与信息差总表、上一章正文全文、"
    "交接文档第三节提到本章的条目、主线.md 第一节、地理.md 大野村格局、社会.md 第零节与总则；"
    "再按第6条按内容加读；章首注里写明读过哪几份（第7条）。"
    "还没读的，先停下读完再写。"
)


def main():
    raw = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace").read()
    try:
        data = json.loads(raw)
    except ValueError:
        return
    path = str((data.get("tool_input") or {}).get("file_path") or "")
    normalized = path.replace("\\", "/")
    if "/正文/" not in normalized and not normalized.startswith("正文/"):
        return
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": REMINDER,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=True))


if __name__ == "__main__":
    main()

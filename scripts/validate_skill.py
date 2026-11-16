#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Skill 校验：frontmatter 完整性 + 目录约定。

发布前跑：python3 scripts/validate_skill.py skills/<name>
CI 全量：  python3 scripts/validate_skill.py --all
"""
import re
import sys
from pathlib import Path

REQUIRED_FIELDS = ["name", "description"]
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")


def parse_frontmatter(text: str) -> dict:
    """解析 YAML frontmatter（只取顶层 key: value，足够 skill 元数据用）"""
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    fields = {}
    for line in m.group(1).splitlines():
        kv = re.match(r"^([a-zA-Z_-]+):\s*(.+)$", line)
        if kv:
            fields[kv.group(1)] = kv.group(2).strip().strip('"').strip("'")
    return fields


def validate(skill_dir: Path) -> list[str]:
    errors = []
    md = skill_dir / "SKILL.md"
    if not md.is_file():
        return [f"{skill_dir}: 缺 SKILL.md"]

    fields = parse_frontmatter(md.read_text(encoding="utf-8"))
    for field in REQUIRED_FIELDS:
        if not fields.get(field):
            errors.append(f"{md}: frontmatter 缺 {field}")

    name = fields.get("name", "")
    if name and not NAME_RE.match(name):
        errors.append(f"{md}: name '{name}' 不合规范（小写字母数字连字符，2-64 字符）")
    if name and name != skill_dir.name:
        errors.append(f"{md}: name '{name}' 与目录名 '{skill_dir.name}' 不一致")

    desc = fields.get("description", "")
    if desc and len(desc) > 1024:
        errors.append(f"{md}: description 过长（{len(desc)} > 1024），路由用描述应精炼")

    scripts = skill_dir / "scripts"
    if scripts.is_dir():
        for py in scripts.glob("*.py"):
            try:
                compile(py.read_text(encoding="utf-8"), str(py), "exec")
            except SyntaxError as e:
                errors.append(f"{py}: 语法错误 {e}")

    # 禁止机器绝对路径（市场分发必须可移植）
    for f in [md, *skill_dir.glob("scripts/*")]:
        if f.is_file() and re.search(r"/home/[A-Za-z0-9_.-]+/", f.read_text(encoding="utf-8", errors="ignore")):
            errors.append(f"{f}: 含机器绝对路径 /home/...，市场分发必须可移植")
    return errors


def main():
    args = sys.argv[1:]
    root = Path(__file__).resolve().parent.parent
    if args and args[0] == "--all":
        targets = sorted(p for p in (root / "skills").iterdir() if p.is_dir())
    elif args:
        targets = [Path(a) for a in args]
    else:
        print(__doc__)
        sys.exit(2)

    failed = False
    for t in targets:
        errors = validate(t)
        if errors:
            failed = True
            print(f"FAIL {t.name}")
            for e in errors:
                print(f"  - {e}")
        else:
            print(f"OK   {t.name}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

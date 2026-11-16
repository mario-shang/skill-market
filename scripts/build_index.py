#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描 skills/ 生成静态索引 index.json（服务直接托管，无需数据库）。

每次发布后跑（或由 publish 脚本自动触发）：
  python3 scripts/build_index.py
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from validate_skill import parse_frontmatter  # noqa: E402


def git_last_commit(path: Path) -> str | None:
    try:
        return subprocess.run(
            ["git", "log", "-1", "--format=%h %ci", "--", str(path.relative_to(ROOT))],
            capture_output=True, text=True, cwd=ROOT, timeout=10
        ).stdout.strip() or None
    except Exception:
        return None


def build() -> dict:
    skills = []
    for d in sorted((ROOT / "skills").iterdir()):
        if not d.is_dir():
            continue
        md = d / "SKILL.md"
        if not md.is_file():
            continue
        fields = parse_frontmatter(md.read_text(encoding="utf-8"))
        files = sorted(str(f.relative_to(d)) for f in d.rglob("*") if f.is_file())
        blob = subprocess.run(
            ["tar", "-czf", "-", "-C", str(d.parent), d.name],
            capture_output=True, timeout=30
        ).stdout
        skills.append({
            "name": fields.get("name", d.name),
            "description": fields.get("description", ""),
            "version": fields.get("version", "0.0.0"),
            "skill_dir": d.name,
            "files": files,
            "file_count": len(files),
            "download": f"/skills/{d.name}/download",
            "updated_at": git_last_commit(d),
            "tar_sha256": hashlib.sha256(blob).hexdigest(),
        })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(skills),
        "skills": skills,
    }


if __name__ == "__main__":
    index = build()
    out = ROOT / "index.json"
    out.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"index.json: {index['count']} skills -> {out}")

# -*- coding: utf-8 -*-
"""Skill Market 只读托管服务。

2C2G 定位：纯静态分发（索引 + tar 下载），无数据库、无写接口、无认证。
发布走 git，服务只读 skills/ 与 index.json，重启即生效。
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
INDEX = ROOT / "index.json"

app = FastAPI(title="skill-market", docs_url=None, redoc_url=None)


def _tar_skill(skill_dir: Path) -> bytes:
    """打包单个 skill 目录为 tar.gz（TAR_PREFIX 内编入顶层目录名）"""
    import subprocess
    return subprocess.run(
        ["tar", "-czf", "-", "-C", str(skill_dir.parent), skill_dir.name],
        capture_output=True, timeout=30, check=True,
    ).stdout


@app.get("/index.json")
def get_index():
    if not INDEX.is_file():
        raise HTTPException(404, "index.json 不存在：先跑 scripts/build_index.py")
    return Response(content=INDEX.read_bytes(), media_type="application/json")


@app.get("/skills")
def list_skills():
    """人类可读列表（与 index.json 同源）"""
    import json
    if not INDEX.is_file():
        raise HTTPException(404, "index.json 不存在：先跑 scripts/build_index.py")
    skills = json.loads(INDEX.read_text(encoding="utf-8")).get("skills", [])
    return {"count": len(skills),
            "skills": [{"name": s["name"], "description": s["description"],
                        "version": s["version"], "download": s["download"]} for s in skills]}


@app.get("/{name}/download")
def download_skill(name: str):
    d = SKILLS_DIR / name
    # 目录名白名单字符校验，防路径穿越
    if not d.is_dir() or name != d.resolve().name or "/" in name or ".." in name:
        raise HTTPException(404, f"skill '{name}' 不存在")
    return Response(
        content=_tar_skill(d),
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="{name}.tar.gz"'},
    )


@app.get("/health")
def health():
    return {"ok": True, "skills": len([p for p in SKILLS_DIR.iterdir() if p.is_dir()])}

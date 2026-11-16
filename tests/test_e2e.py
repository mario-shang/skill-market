# -*- coding: utf-8 -*-
"""端到端冒烟：校验 → 索引 → 起服务 → 索引/下载/解压 → 装好的 skill 结构正确。

跑法：cd skill-market && python3 tests/test_e2e.py
依赖：仅标准库 + uvicorn/fastapi（服务端）；curl 或 urllib。
"""
import json
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 8391
BASE = f"http://127.0.0.1:{PORT}"


def _python() -> str:
    """选一个有 uvicorn 的解释器：优先项目 venv，回落 sys.executable"""
    venv = ROOT / ".venv/bin/python"
    for py in [str(venv) if venv.exists() else None, sys.executable]:
        if py and subprocess.run([py, "-c", "import uvicorn, fastapi"], cwd=ROOT,
                                 capture_output=True, timeout=15).returncode == 0:
            return py
    raise SystemExit("无含 uvicorn 的解释器（pip install fastapi uvicorn）")


def sh(*cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=60, **kw)
    if r.returncode != 0:
        print(r.stdout, r.stderr)
        raise SystemExit(f"命令失败: {' '.join(cmd)}")
    return r.stdout


def main():
    # 1. 校验
    print(sh("python3", "scripts/validate_skill.py", "--all").strip())

    # 2. 索引
    print(sh("python3", "scripts/build_index.py").strip())
    py = _python()

    # 3. 起服务（后台）
    proc = subprocess.Popen(
        [py, "-m", "uvicorn", "server.app:app", "--port", str(PORT)],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        import time
        for _ in range(30):
            try:
                urllib.request.urlopen(f"{BASE}/health", timeout=1)
                break
            except Exception:
                time.sleep(0.3)
        else:
            raise SystemExit("服务未就绪")

        # 4. 索引可达
        index = json.load(urllib.request.urlopen(f"{BASE}/index.json"))
        names = [s["name"] for s in index["skills"]]
        print(f"index: {index['count']} skills {names}")
        assert "homework-collector" in names

        # 5. 下载 + 解压 = 可安装
        blob = urllib.request.urlopen(f"{BASE}/skills/homework-collector/download").read()
        with tempfile.TemporaryDirectory() as td:
            tgz = Path(td) / "s.tar.gz"
            tgz.write_bytes(blob)
            with tarfile.open(tgz) as tf:
                tf.extractall(td)  # noqa: S202 受控源（自家 skills/）
            installed = Path(td) / "homework-collector"
            assert (installed / "SKILL.md").is_file()
            assert (installed / "scripts" / "render_homework.py").is_file()
            print(f"download: {len(blob)} bytes, 解压结构 OK")

        # 6. 404 防穿越
        try:
            urllib.request.urlopen(f"{BASE}/skills/..%2fetc/download")
            raise SystemExit("路径穿越未被拦截")
        except urllib.error.HTTPError as e:
            assert e.code == 404
            print("traversal: 404 OK")
    finally:
        proc.terminate()

    print("E2E PASS")


if __name__ == "__main__":
    main()

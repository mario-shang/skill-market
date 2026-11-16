# Skill Market

个人 skill 市场：skill 以「SKILL.md + scripts/」为发布单元，git push 即上架，2C2G 静态托管。
通用 agent 拿到地址后：查索引 → 挑 skill → 下载 tar → 解压到本地 skills 目录即装完。

## 布局

```
skills/<name>/          # 发布单元：SKILL.md（frontmatter: name/version/description）+ scripts/（可选）
index.json              # 自动生成的静态索引（build_index.py），服务直接托管
scripts/build_index.py  # 扫描 skills/ 重建索引
scripts/validate_skill.py  # 发布前校验：frontmatter / 目录一致性 / 语法 / 可移植性（禁机器绝对路径）
server/app.py           # FastAPI 只读托管（2C2G 内存占用 ~40MB）
deploy/                 # systemd unit + 部署说明
tests/                  # 端到端冒烟
```

## Agent 接入协议（给 agent 的三句话）

1. `GET {BASE}/index.json` 拿索引（name/description/version/download）。
2. 按 description 自判或用户指定哪个 skill 要装。
3. `GET {BASE}/skills/{name}/download` 下 tar.gz，解压到自己的 skills 目录（如 `~/.claude/skills/<name>/`），按其 SKILL.md 使用。

curl 一条龙：

```bash
curl -s {BASE}/index.json | jq -r '.skills[] | "\(.name): \(.description)"'
curl -sL {BASE}/skills/homework-collector/download | tar xz -C ~/.claude/skills/
```

## 发布流程

```bash
# 1. 新建 skills/<name>/SKILL.md（+ 可选 scripts/）
# 2. 校验 + 重建索引
python3 scripts/validate_skill.py skills/<name>
python3 scripts/build_index.py
# 3. git commit + push（部署机 git pull 即上架；或 CI 跑同两步）
```

## 约束（写进 skill 审核习惯，validate_skill.py 强制）

- frontmatter 必填 name/description；name 与目录名一致（路由与安装目录依赖）。
- description ≤1024 字符，写给 agent 路由用——触发词要显式。
- 一切机器绝对路径禁止（skill 必须可移植）；脚本语法编译检查。
- skills 之间不互相引用；需要共享就复制（skill 是独立分发单元）。

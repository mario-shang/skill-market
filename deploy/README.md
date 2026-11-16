# 部署（2C2G 云主机）

```bash
# 1. 拉代码
git clone <repo> /opt/skill-market && cd /opt/skill-market
python3 -m venv .venv && .venv/bin/pip install fastapi uvicorn
.venv/bin/python scripts/build_index.py

# 2. 服务
cp deploy/skill-market.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now skill-market
curl -s localhost:8300/health

# 3. 对外（推荐 caddy，自动 TLS；2C2G 内存 ~30MB）
#    Caddyfile:
#      skills.example.com {
#          reverse_proxy 127.0.0.1:8300
#      }
```

## 更新上架

```bash
cd /opt/skill-market && git pull && .venv/bin/python scripts/build_index.py
# 服务只读托管文件，索引/新 skill 目录 pull 后即生效，无需重启
# （索引内容由 build_index.py 重写——若 systemd 只读限制挡住写入，在本机先 build 后 push，
#  部署机纯 pull；本仓库约定 index.json 随提交入库）
```

## 资源占用（实测口径）

- uvicorn 常驻 ~40MB、caddy ~30MB：合计 <100MB，2C2G 余量充足。
- tar 打包按请求即时执行（单 skill <100KB，亚秒级）；若 skill 数量上百再考虑预打包缓存。

# CVM Monitor Dashboard

一个基于 `FastAPI + Vue 3` 的腾讯云 CVM 监控展示项目，聚焦以下指标：

- CPU 使用率
- 内存使用率
- 入带宽 / 出带宽
- 磁盘使用率

## 目录结构

```text
backend/   FastAPI 后端，封装腾讯云监控接口
frontend/  Vue 3 前端，展示监控看板
```

## 后端启动

```bash
cd /Users/kong/dev/moniServer/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

需要在 `.env` 中配置：

- `TENCENT_SECRET_ID`
- `TENCENT_SECRET_KEY`
- `TENCENT_REGION`
- `DEFAULT_INSTANCE_ID`

## 前端启动

```bash
cd /Users/kong/dev/moniServer/frontend
npm install
npm run dev
```

前端开发地址默认为 `http://localhost:5173`，会自动代理到后端 `http://127.0.0.1:8000`。

## API

### `GET /api/monitor/config`

返回默认实例和支持的指标。

### `GET /api/monitor/dashboard`

查询参数：

- `instanceId`: CVM 实例 ID
- `rangeHours`: 最近多少小时，默认 6
- `startTime`: 可选，自定义开始时间
- `endTime`: 可选，自定义结束时间
- `period`: 可选，查询粒度，单位秒

返回聚合后的卡片数据和时序数据，前端可直接渲染。

## 说明

- 前端不直接访问腾讯云 API，避免泄露密钥。
- 后端统一聚合多个指标，后续接缓存和告警会更方便。
- 当前实现只面向 `QCE/CVM`。

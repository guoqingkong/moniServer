# moniServer

一个基于 `FastAPI + Vue 3` 的腾讯云监控看板，当前覆盖：

- `CVM` 实例运行监控
- `COS` 存储监控
- `SQLite` 本地时序存储
- `5 分钟` 后台采集入库
- 公网带宽阈值告警与邮件通知
- `30 分钟 / 6 小时 / 日对比 / 周对比` 分析视图

## 当前能力

### 监控资源

- `CVM`
  - CPU 使用率
  - 内存使用率
  - 公网入带宽
  - 公网出带宽
  - 磁盘使用率
- `COS`
  - 标准存储容量
  - 标准对象数量
  - 外网上行带宽
  - 外网下行带宽
  - `GET` 请求数
  - `PUT` 请求数

### 页面结构

- `CVM 监控`
  - 两台主机的实时卡片和趋势图
- `CVM 分析`
  - 时间窗切换
  - 当前窗口 vs 上一窗口对比图
  - 最近告警
- `COS 存储`
  - 两个 bucket 的实时卡片和趋势图
- `COS 存储分析`
  - 时间窗切换
  - 当前窗口 vs 上一窗口对比图

### 数据策略

- 页面自动刷新：`60 秒`
- 后台采集入库：`300 秒`
- 带宽告警巡检：`300 秒`
- 监控数据优先读本地 `SQLite`
- 本地数据不足时再回源腾讯云补库

## 项目结构

```text
backend/
  app/
    api/          FastAPI 接口
    clients/      腾讯云 API 客户端
    services/     监控聚合、采集、告警服务
    schemas/      Pydantic 模型
    db.py         SQLite 初始化与连接
    repositories.py
frontend/
  src/
    api/          前端接口封装
    components/   图表、卡片组件
    views/        看板页面
```

## 环境要求

- Python `3.9+`
- Node.js `18+`
- 腾讯云监控 API 可用凭据
- 如果开启邮件告警，需要可用 SMTP 账户

## 后端启动

```bash
cd /Users/kong/dev/moniServer/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 前端启动

```bash
cd /Users/kong/dev/moniServer/frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

开发地址：

- 前端：[http://127.0.0.1:5173](http://127.0.0.1:5173)
- 后端：[http://127.0.0.1:8000](http://127.0.0.1:8000)

## `.env` 主要配置

基础配置：

- `TENCENT_SECRET_ID`
- `TENCENT_SECRET_KEY`
- `TENCENT_REGION`
- `DEFAULT_INSTANCE_ID`
- `MONITOR_INSTANCE_IDS`
- `MONITOR_COS_BUCKET_NAMES`
- `CORS_ORIGINS`
- `SQLITE_DB_PATH`

采集与告警：

- `METRICS_COLLECTION_POLL_SECONDS`
- `METRICS_COLLECTION_LOOKBACK_MINUTES`
- `BANDWIDTH_ALERT_THRESHOLD_MBPS`
- `BANDWIDTH_ALERT_POLL_SECONDS`
- `BANDWIDTH_ALERT_RECIPIENT`
- `BANDWIDTH_ALERT_LOG_PATH`
- `BANDWIDTH_ALERT_STATE_PATH`

邮件发送：

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_USE_SSL`

默认示例见 [backend/.env.example](/Users/kong/dev/moniServer/backend/.env.example)。

## SQLite 说明

默认数据库文件：

- [backend/data/monitor.db](/Users/kong/dev/moniServer/backend/data/monitor.db)

当前主要表：

- `metric_points`
  - 监控时序点
- `alert_events`
  - 告警事件
- `poll_runs`
  - 后台采集与巡检执行记录

## 后端接口

### 基础配置

- `GET /api/monitor/config`
  - 返回实例列表、COS bucket 列表、默认时间范围

### 实时看板

- `GET /api/monitor/dashboard`
  - CVM 实时看板
- `GET /api/monitor/cos/dashboard`
  - COS 实时看板

### 历史分析

- `GET /api/monitor/history`
  - 读取 SQLite 历史时序
- `GET /api/monitor/compare`
  - 比较两个时间窗口的均值和峰值

### 采集与告警

- `GET /api/monitor/alerts/recent`
  - 最近告警
- `GET /api/monitor/collector/status`
  - 最近一次采集状态、下一次采集时间、写入点数
- `GET /health`
  - 服务健康状态

## 告警逻辑

- 监控对象：指定 `CVM` 实例
- 监控指标：公网入带宽 / 公网出带宽
- 阈值：默认 `50 Mbps`
- 规则：任一检查点超过阈值即记录一次
- 去重：同实例、同指标、同时间点不会重复告警
- 动作：
  - 写入 `SQLite`
  - 写入 `jsonl` 日志
  - 如果 SMTP 已配置则发送邮件

## 说明

- 前端不直接访问腾讯云 API，避免密钥暴露。
- 分析页即使历史数据不满 `6 小时`、`1 天` 或 `1 周`，也会保留图表并显示已有数据。
- `SQLite` 现在是本地查询底座，适合做趋势分析和对比；后续如果要多实例部署，再考虑迁移到 `PostgreSQL`。

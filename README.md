# 连锁门店经营数据分析平台

基于 Python + FastAPI + Vue 3 + PostgreSQL + ECharts 构建的多源数据分析平台，支持销售、库存、会员、促销、客流、天气数据的导入、清洗、分析与可视化。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2 |
| 前端 | Vue 3, Vite, Pinia, Element Plus, ECharts 5 |
| 数据库 | PostgreSQL 16 |
| 部署 | Docker Compose |

## 功能清单

- **数据导入**: CSV/Excel 大文件分块上传，后台异步处理，SSE 进度推送
- **数据清洗**: 脏数据校验（正则+类型+范围）、重复数据去重（业务键 upsert）、缺失时段检测
- **指标建模**: GMV、客单价、坪效、订单量等 KPI 实时计算
- **门店排名**: 按 GMV/订单量/客单价多维排名
- **消费者分群**: RFM 模型 + 分位数打分，自动分为5群
- **趋势预测**: Holt-Winters 指数平滑 + 天气/促销因子修正 + 置信区间
- **异常检测**: IQR 法 + Z-Score + 同比偏离度
- **报表导出**: Excel/CSV 格式，按门店/日期/指标灵活导出
- **权限控制**: RBAC + 门店级数据隔离，JWT 认证
- **任务日志**: 导入任务全生命周期追踪

## 项目结构

```
├── backend/                # FastAPI 后端
│   ├── app/
│   │   ├── main.py        # 应用入口
│   │   ├── config.py      # 配置管理
│   │   ├── database.py    # 数据库连接
│   │   ├── models/        # ORM 模型 (14张表)
│   │   ├── schemas/       # Pydantic 模型
│   │   ├── api/           # 路由层 (12个模块)
│   │   ├── services/      # 业务逻辑层
│   │   ├── core/          # 安全与权限
│   │   └── utils/         # 工具函数
│   ├── tests/             # 测试用例
│   ├── alembic/           # 数据库迁移
│   └── requirements.txt
├── frontend/              # Vue 3 前端
│   ├── src/
│   │   ├── views/         # 页面 (9个视图)
│   │   ├── components/    # 组件
│   │   ├── stores/        # Pinia 状态
│   │   ├── api/           # Axios 封装
│   │   └── router/        # 路由
│   └── package.json
├── docker-compose.yml
└── .env.example
```

## 数据库设计

共14张核心表：

| 表名 | 说明 | 关键索引/约束 |
|------|------|---------------|
| users | 用户表 | username UNIQUE |
| roles | 角色表 (admin/manager/viewer) | name UNIQUE |
| user_store_permissions | 用户-门店权限映射 | (user_id, store_id) |
| stores | 门店表 | code UNIQUE |
| sales | 销售流水表 | (store_id, receipt_no, item_id) UNIQUE |
| inventory | 库存快照表 | (store_id, item_id, snapshot_date) UNIQUE |
| members | 会员表 | member_no UNIQUE, GIN(tags) |
| member_transactions | 会员消费记录 | (member_id, transaction_date) |
| promotions | 促销活动表 | (store_id, promo_code) UNIQUE |
| traffic | 客流表 | (store_id, traffic_date, hour) UNIQUE |
| weather | 天气数据表 | (city, weather_date) UNIQUE |
| import_tasks | 导入任务表 | user_id |
| task_logs | 任务日志表 | task_id |
| data_quality_logs | 数据质量日志 | (store_id, issue_type) |

## API 接口

### 认证 `/api/auth`
- `POST /login` - 登录获取 JWT Token
- `POST /register` - 注册用户（需指定角色和门店权限）
- `GET /me` - 获取当前用户信息

### 数据导入 `/api/imports`
- `POST /upload` - 上传文件（支持 CSV/Excel）
- `GET /{task_id}/status` - 查询导入进度
- `GET /history` - 导入历史记录

### 数据查询（均支持分页和门店权限过滤）
- `GET /api/sales` - 销售数据
- `GET /api/inventory` - 库存数据
- `GET /api/members` - 会员数据
- `GET /api/promotions` - 促销活动
- `GET /api/traffic` - 客流数据
- `GET /api/weather` - 天气数据

### 分析 `/api/analytics`
- `GET /kpi` - KPI 指标计算
- `GET /ranking` - 门店排名
- `GET /segmentation` - RFM 消费者分群
- `GET /forecast` - 趋势预测（Holt-Winters）
- `GET /anomalies` - 异常检测
- `GET /missing-periods` - 缺失时间段检测

### 报表 `/api/reports`
- `POST /export` - 生成报表
- `GET /{report_id}/download` - 下载报表

### 任务日志 `/api/tasks`
- `GET /` - 任务列表
- `GET /{task_id}/logs` - 任务详细日志

## 核心算法

### 数据清洗流水线
```
原始数据 → 列名标准化 → 全空行删除 → 完全重复行去除 → 必填字段校验
→ 类型强转(to_numeric) → 范围检查(quantity>0) → 日期格式化 → 入库(ON CONFLICT DO NOTHING)
```

### 大文件导入优化
- pandas `chunksize=10000` 分批读取
- asyncio 异步后台任务
- PostgreSQL `ON CONFLICT DO NOTHING` 批量去重
- 实时更新导入进度

### RFM 消费者分群
1. 计算 R (Recency)、F (Frequency)、M (Monetary)
2. 按分位数(25/50/75)打分(1-4分)
3. 映射到5个业务分群：重要价值/重要保持/一般价值/一般发展/流失

### Holt-Winters 趋势预测
1. 初始化水平、趋势和周期性(7天)因子
2. 迭代更新三个分量 (α=0.3, β=0.1, γ=0.2)
3. 天气修正：强降水(-15%)、中度降水(-7%)
4. 促销修正：活动期间 boost = 1 + discount_rate * 0.5
5. 滚动回测计算 MAPE 评估预测精度
6. 95%置信区间随预测步数扩大

### 异常检测
- **IQR法**: Q1 - 1.5*IQR ~ Q3 + 1.5*IQR 范围外标记异常
- **同比法**: 当日 vs 去年同日偏离 >50% 触发告警
- **库存法**: 实际库存 vs 最小/最大库存阈值比较

### 权限控制（防越权）
1. JWT Token 携带 user_id + role
2. API 层 `get_current_user_with_stores` 注入授权门店列表
3. 每个查询拼接 `WHERE store_id IN (authorized_stores)`
4. 非授权门店访问返回 403

## 测试方案

```bash
cd backend
pip install pytest pytest-asyncio httpx aiosqlite
pytest tests/ -v
```

测试覆盖：
- 认证流程（注册/登录/Token校验）
- 数据清洗（有效数据/脏数据/重复/缺失字段）
- 权限控制（admin全量/viewer受限/越权拒绝）
- 导入流程（上传→任务创建→状态查询）
- 预测算法（基本预测/数据不足/置信区间递增）

## 启动步骤

### 方式一：Docker Compose（推荐）

```bash
# 克隆项目后
cp .env.example .env

# 启动所有服务
docker-compose up -d

# 访问
# 后端 API: http://localhost:8000/docs
# 前端页面: http://localhost:5173
```

### 方式二：本地开发

```bash
# 1. 启动 PostgreSQL（需要本地安装或使用Docker）
docker-compose up -d postgres

# 2. 后端
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 3. 前端
cd frontend
npm install
npm run dev

# 访问
# Swagger 文档: http://localhost:8000/docs
# 前端页面: http://localhost:5173
```

### 初始化数据

首次启动后，通过 API 创建初始角色和管理员：

```bash
# 应用启动时自动创建表，需手动插入角色
psql -U postgres -d store_analytics -c "
INSERT INTO roles (id, name, description) VALUES
  (1, 'admin', '管理员'),
  (2, 'manager', '店长'),
  (3, 'viewer', '查看者')
ON CONFLICT DO NOTHING;
"

# 注册管理员
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","email":"admin@example.com","password":"Admin123456","role_id":1}'
```

## 关键问题解决方案

| 问题 | 解决方案 |
|------|----------|
| 脏数据 | 多级校验：正则→类型强转→范围检查→业务规则 |
| 重复数据 | DataFrame去重 + DB唯一约束 + ON CONFLICT DO NOTHING |
| 数据缺失时段 | generate_series对比检测缺口，记入data_quality_logs |
| 大文件导入慢 | chunksize分批 + 异步后台任务 + 进度推送 |
| 预测偏离实际 | 滚动回测MAPE + 天气/促销修正 + 置信区间展示 |
| 越权查看 | JWT认证 + 门店权限注入 + 查询条件强制过滤 |

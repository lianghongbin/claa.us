# 轻量财务管理系统

基于 Django 与 Django Admin（[django-simpleui](https://github.com/newpanjing/simpleui)）的公司内部收支、应收应付、对账与报表后台。适合小公司单机或内网部署。**不含多账户/总账模块**，以流水 + 账单 + 轻量报表为主。

## 功能概览

### 基础数据

| 模块 | 说明 |
|------|------|
| **科目分类** | 收入 / 支出科目；财务管理员可增删改，普通财务只读。 |
| **项目** | 可选归属项目；支持「可见分组」控制谁能看到该项目。 |
| **标签** | 流水多选标签。 |
| **往来单位** | 客户 / 供应商 / 二者；支持可见分组。 |

### 收入 / 支出明细

- 后台分为两个菜单（`IncomeTransaction` / `ExpenseTransaction` 代理模型，同一张 `Transaction` 表）。
- 字段：日期、科目、金额、账户名称、项目、往来单位、标签、备注、对账标记、凭证附件等。
- **新增页**不展示空审计字段；**编辑页**显示创建人、创建/更新时间。
- 列表支持筛选；顶部显示**当前筛选**下的收入/支出汇总。
- 批量操作：将选中记录标记为已对账（写操作日志）。
- **导入导出**：[django-import-export](https://github.com/django-import-export/django-import-export) + Excel（`openpyxl`）。

### 应收 / 应付

| 模块 | 说明 |
|------|------|
| **应收账单** | 单号、客户、账期、金额、状态（草稿/待收/部分/已结清/作废）；`amount_paid` 由核销自动汇总。 |
| **收款核销** | 收入流水 ↔ 应收；可在账单或流水侧维护分配行。 |
| **应付账单** | 含**审批状态**（草稿/待审批/已批准/已驳回）与付款状态；仅**已批准**可付款核销。 |
| **付款核销** | 支出流水 ↔ 应付。 |
| **应付审批** | 需 `finance.approve_apinvoice` 或属于「财务管理员」/超级用户。 |

应收账单同样支持「可见分组」；自定义权限 `view_all_arinvoices` / `view_all_apinvoices` 可查看全部账单。

### 银行对账

| 模块 | 说明 |
|------|------|
| **对账批次 / 明细** | CSV 导入（UTF-8 / GBK，中英文表头）；明细与系统流水匹配。 |
| **自动 / 手工匹配** | 按金额、日期等规则建议匹配；匹配后系统流水 `is_reconciled=True`。 |
| **对账差异** | 手续费、尾差、有账未记账、已记账未到账等；可生成调整流水并回写匹配。 |

### 报表与看板

需具备 `finance.view_incometransaction`（或超级用户）方可访问；数据范围与流水列表一致（项目/往来可见分组 + `view_all_*`）。

| 入口 | URL（相对站点根） | 说明 |
|------|-------------------|------|
| **财务看板** | `/admin/finance/dashboard/` | 近 6 个月收支趋势（按月）、收入/支出分类占比 |
| **财务报表** | `/admin/finance/reports/` | 报表索引 |
| 损益表 | `/admin/finance/reports/profit-loss/` | 按期间、科目、项目汇总 |
| 现金流量表 | `/admin/finance/reports/cash-flow/` | 期间经营现金流入/流出（轻量直接法） |
| 资产负债表 | `/admin/finance/reports/balance-sheet/` | 货币资金、应收、应付、累计盈余（轻量口径） |
| 现金流预测 | `/admin/finance/reports/cash-flow-forecast/` | 按应收/应付**约定到期日**汇总未结清余额 |

收入明细列表页提供「财务看板」「财务报表」快捷按钮。

### 审计与用户

- **操作日志**：`AuditLog` 记录创建、修改、删除、对账等（仅财务管理员与超级用户只读查看）。
- **用户**：邮箱登录；新建用户可邮件发送初始密码；支持首次登录强制改密。

## 权限与数据范围

### 预设分组

执行 `python manage.py setup_finance_groups` 创建（可重复执行，幂等）：

| 分组 | 能力摘要 |
|------|----------|
| **财务管理员** | 科目/项目/标签/往来全权；全部 `view_all_*`；应收应付与核销全权；应付审批；银行对账与差异；收入/支出增删改查；操作日志；用户与 Django 组管理。 |
| **普通财务** | 收入/支出增改查（不可删）；科目/项目/标签/往来只读；应收应付与核销（不可删应付账单、不可审批）；对账明细匹配与差异登记；**无**操作日志、**无**用户管理、**无** `view_all_*`。 |

将用户勾选「职员状态」并加入上述分组之一（超级用户不受分组限制）。

### 可见分组（行级范围）

在 **项目**、**往来单位**、**应收账单** 上可配置「可见分组」（M2M → `auth.Group`）：

- **不选**：所有具备对应 `view_*` 权限的用户均可见。
- **已选**：仅所选分组内的用户可见；用户未加入任何分组时，只能看到「未限制」的记录。

流水列表额外按**项目**与**往来单位**的可见性过滤（与收入/支出菜单一致）。

### 跨组查看（自定义权限）

授予下列权限可**忽略**可见分组（超级用户始终全部可见）：

| 权限 codename | 作用 |
|---------------|------|
| `finance.view_all_projects` | 查看全部项目 |
| `finance.view_all_counterparties` | 查看全部往来单位 |
| `finance.view_all_finance_transactions` | 查看全部流水（忽略项目/往来过滤） |
| `finance.view_all_arinvoices` | 查看全部应收账单 |
| `finance.view_all_apinvoices` | 查看全部应付账单 |

另：`finance.approve_apinvoice` — 审批应付账单（不含于普通财务默认权限）。

实现细节见 [`apps/finance/permissions.py`](apps/finance/permissions.py)、[`apps/finance/visibility.py`](apps/finance/visibility.py)。

## 统一入口与菜单

- 站点根 `/` 重定向至 `/admin/`。
- 侧边栏由 [`config/simpleui_menus.py`](config/simpleui_menus.py) 按业务分组（概览、记账、基础资料、应收、应付、对账、审计、系统）；各项配置独立图标，并按 Django 权限过滤可见菜单。

## 环境要求

- **Python 3.11**（推荐；[`.python-version`](.python-version) 供 pyenv / asdf）
- 默认 **SQLite**；可选 **PostgreSQL**（`psycopg` / `psycopg2-binary` + `.env` 中 `POSTGRES_*`）

若曾用其它 Python 版本创建虚拟环境：`rm -rf .venv && ./scripts/install.sh`。

## 快速安装

```bash
./scripts/install.sh
source .venv/bin/activate
python manage.py migrate
python manage.py createsuperuser   # 电子邮箱 + 密码
python manage.py setup_finance_groups
python manage.py runserver
```

访问 `http://127.0.0.1:8000/`（跳转后台）或 `http://127.0.0.1:8000/admin/`。

### 一键启动（本机日常）

```bash
chmod +x scripts/*.sh start.command   # 首次克隆后执行一次
./scripts/run.sh
```

或在 Finder 中**双击项目根目录的 `start.command`**（会自动安装依赖、迁移数据库并打开浏览器）。按 `Ctrl+C` 结束服务。

### Docker 部署（推荐：开机自启）

适合「不想本机装 Python / 希望开机自动跑服务」的场景。数据保存在项目目录的 `data/`、`media/`、`backups/`。

**日常更新并启动（推荐）**：

```bash
chmod +x start.sh
./start.sh
```

自动：`docker compose down` → 从 GitHub 拉最新代码 → 释放 8000 端口 → 构建并启动容器。

**另一台机器仅更新部署**（已 `git clone` 过）：

```bash
cd /path/to/claa.us
chmod +x update.sh
./update.sh
```

**首次安装**：

```bash
chmod +x scripts/docker-install.sh
./scripts/docker-install.sh
```

脚本会自动：检查并启动 Docker、生成 `.env`（含管理员账号密码）、构建镜像、迁移数据库、创建超级用户、后台启动服务并打开浏览器。终端会打印登录地址与密码。

若本机未装 Docker Desktop，在 macOS 上会尝试用 Homebrew 安装；安装后请在 Docker Desktop 设置里勾选 **Start when you log in** 以实现登录后自启。

**手动步骤（可选）**：

```bash
cp .env.example .env    # 编辑 SECRET_KEY、ADMIN_EMAIL、ADMIN_PASSWORD
docker compose up -d --build
```

访问 `http://127.0.0.1:8000/admin/`。

**日常**：

| 操作 | 命令 |
|------|------|
| 启动（后台） | `docker compose up -d` |
| 停止 | `docker compose down` |
| 查看日志 | `docker compose logs -f web` |
| 重建镜像 | `docker compose up -d --build` |

`docker-compose.yml` 中已设置 `restart: unless-stopped`：只要 Docker Desktop 在运行，容器会在崩溃或重启后自动拉起。

**从本机 SQLite 迁到 Docker**：把现有 `db.sqlite3` 复制为 `data/db.sqlite3`，再执行 `docker compose up -d`。

**Cloudflare Tunnel**：默认已允许 `fin.skyvl.com` 与 `CSRF_TRUSTED_ORIGINS=https://fin.skyvl.com`；换域名时改 `.env` 或 `config/settings/base.py` 中的 `_TUNNEL_HOSTS`。

**局域网访问**：在 `.env` 的 `ALLOWED_HOSTS` 中加入本机 IP，例如 `127.0.0.1,localhost,192.168.1.20`。

### 复制到另一台 Mac

1. **拷贝项目**（任选其一）  
   - Git：`git clone <仓库地址>`  
   - U 盘 / 网盘：在本机打包后拷贝：
     ```bash
     ./scripts/package-transfer.sh              # 仅代码
     ./scripts/package-transfer.sh --with-db    # 含 SQLite 数据
     ./scripts/package-transfer.sh --with-db --with-media   # 含数据库与附件
     ```
   - **不要**复制 `.venv`（另一台 Mac 需重新安装，架构可能不同）。

2. **新 Mac 前置条件**  
   - 安装 [Python 3.11](https://www.python.org/downloads/)（或 `brew install python@3.11`）。  
   - 终端执行：`chmod +x scripts/*.sh start.command`

3. **首次在新电脑**  
   ```bash
   cd claa.us          # 进入解压后的项目目录
   ./scripts/install.sh
   python manage.py createsuperuser   # 若未使用 --with-db 拷贝旧库
   ```

4. **之后每次使用**  
   - 双击 `start.command`，或终端执行 `./scripts/run.sh`。

5. **数据库备份 / 还原（SQLite）**  
   - 后台：**系统管理 → 系统设置**（仅超级用户或已授予「备份与还原数据库」权限的账号）。  
   - 命令行：`python manage.py backup_database`、`python manage.py restore_database --latest`  
   - Shell：`./scripts/backup_db.sh`、`./scripts/restore_db.sh --latest`

6. **若要沿用本机数据**  
   - 打包时加 `--with-db`（及可选 `--with-media`），或手动复制 `db.sqlite3`、`media/` 到新项目目录。  
   - 已有数据库时**无需**再执行 `createsuperuser`（除非库为空）。

7. **局域网其他设备访问**（可选）  
   ```bash
   FINANCE_HOST=0.0.0.0 FINANCE_PORT=8000 ./scripts/run.sh
   ```
   并在 `.env` 的 `ALLOWED_HOSTS` 中加入该 Mac 的 IP。

在「用户与账号 → 用户」中：勾选职员状态，加入「财务管理员」或「普通财务」。

### 常用管理命令

| 命令 | 说明 |
|------|------|
| `python manage.py setup_finance_groups` | 创建/更新「财务管理员」「普通财务」分组及权限绑定 |
| `python manage.py backup_database` | 将 SQLite 备份到 `backups/`（与后台「一键备份」相同） |
| `python manage.py restore_database --latest` | 从 `backups/` 最新文件还原 SQLite |
| `./update.sh` | **另一台机器**：拉取最新代码并重启 Docker（不打开浏览器） |
| `./start.sh` | 更新代码 + 重启 Docker（本机，可打开浏览器） |
| `./scripts/docker-install.sh` | Docker 首次安装（不拉 git） |
| `docker compose up -d` | Docker 后台启动服务 |
| `docker compose exec web python manage.py …` | 在容器内执行管理命令 |
| `python manage.py test apps.finance` | 运行财务模块单元测试 |
| `python manage.py check` | Django 系统检查 |

## 配置说明

复制 [`.env.example`](.env.example) 为 `.env`：

| 变量 | 说明 |
|------|------|
| `SECRET_KEY` | 生产环境务必改为长随机字符串 |
| `DEBUG` | 生产设为 `False` |
| `ALLOWED_HOSTS` | 逗号分隔主机名 |
| `POSTGRES_*` | 设置 `POSTGRES_DB` 时使用 PostgreSQL |
| `SQLITE_PATH` | 可选，自定义 SQLite 路径 |
| `MEDIA_ROOT` / 上传 | 流水凭证附件；开发环境 DEBUG 下由 Django 提供媒体文件 |
| `EMAIL_*` | 新建用户初始密码邮件；未配置时默认控制台输出 |
| `SESSION_COOKIE_AGE` | 会话秒数，默认 `3600`（1 小时无操作后需重新登录） |
| `SESSION_COOKIE_SECURE` | HTTPS 访问设为 `True`（Cloudflare Tunnel） |
| `FINANCE_ASSET_VERSION` | 后台 JS/CSS 版本号，改后强刷或清 CDN 缓存 |

**会话**：默认 1 小时无请求自动退出；只要在后台有操作（翻页、保存等）会重新计时。

**标签页关不掉 / 脚本像没更新**：先 `./start.sh`，浏览器 **Cmd+Shift+R**；用 Cloudflare 时到控制台 **Purge Cache**，或把 `.env` 里 `FINANCE_ASSET_VERSION` 改成新值后重启。

从旧版 `auth.User` 迁移后若遇冲突，可删除本地 `db.sqlite3` 后重新 `migrate` 与 `createsuperuser`。

**Python 3.14**：可能需 [`config/django_py314_context_patch.py`](config/django_py314_context_patch.py)；日常请以 **3.11** 为准。

## 导入导出（收入/支出明细）

支持英文字段名或中文列名。必填：`日期`、`科目名称`、`金额`、`账户名称`。在分项菜单下**收支类型**可省略（按页面自动补全）。

| 列 | 说明 |
|----|------|
| `date` / `日期` | `YYYY-MM-DD` |
| `transaction_type` / `收支类型` | 可选；`income`/`expense` 或 `收入`/`支出` |
| `category_name` / `科目名称` | 须与科目及类型一致 |
| `amount` / `金额` | 正数 |
| `account_name` / `账户名称` | 文本 |
| `project_code` / `项目编码` | 可选 |
| `counterparty_code` / `单位编码` | 可选 |
| `tag_names` / `标签` | 可选；逗号分隔 |
| `note` / `备注` | 可选 |
| `is_reconciled` / `已对账` | 可选 |
| `id` | 可选；用于更新 |

导入新建时**创建人**为当前用户。往来单位、项目等另有独立导入资源，见后台各模块「导入」按钮。

## 生产部署注意

- `DEBUG=False`、强 `SECRET_KEY`、`ALLOWED_HOSTS`。
- `python manage.py collectstatic`。
- HTTPS 反向代理保护 `/admin/`。
- 定期备份 SQLite 或 PostgreSQL；备份 `MEDIA_ROOT` 中的附件。

## 项目结构（摘要）

```
manage.py
requirements.txt
config/                    # 设置、URL、可选 py314 补丁
apps/accounts/             # 邮箱用户、首次改密、建用户发邮件
apps/finance/              # 模型、Admin、对账、报表、看板、权限命令
  management/commands/setup_finance_groups.py
  reports.py / dashboard.py / visibility.py / bank_*.py
apps/audit/                # 操作日志
templates/admin/finance/   # 看板、报表、列表汇总模板
scripts/install.sh
```

## 许可证

内部使用；如需开源许可证请自行补充。

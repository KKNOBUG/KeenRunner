#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/11/19 14:00:00
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : repair_legacy_config_data
@DateTime: 2026/11/19 14:00:00

配置名称绑定改造（配置名称绑定改造.md §1.2 缺陷清单 D1~D6）存量数据纠正脚本。
我方与第三方后端项目结构一致，本脚本两端通用：连接信息缺省读本项目 backend/.env，
表前缀自动探测（krun_/tbx_，--prefix 可覆盖），唯一差异由探测吸收，无需维护两份脚本。

覆盖 8f358fc9 以来全部表结构变更对应的存量纠正（迁移 29~32 已做列级 DDL 与回填，
本脚本补齐迁移不覆盖的 JSON 键值与残留缺口，幂等可重跑）：
  表结构变更面：autotest_task（cases_execute_config 引用键化 + task_involve_env_ids 新列）、
  autotest_step（request_config_name→request_config_mode + operates 引用键化）、
  autotest_env_config（config_mode + project_id/env_type 冗余维度）、
  autotest_details（request_config_mode 新列；operates 为独立快照契约不在改造范围）、
  perf_api（request_config_name→request_config_mode）。

修复项：
  R1 env_config：空 config_mode 按（应用+节点+名称忽略大小写）分组生成唯一 mode（迁移30口径）；
     project_id/env_type 冗余维度缺失按绑定回填；
  R2 step/perf_api：request_config_mode 为空时——旧名称列仍在（迁移32未执行）按名称反查回填；
     名称列已删的 step 从已回填任务配置/明细快照恢复；perf_api 无名称来源仅报告；
  R3 task.cases_execute_config：旧名称结构 → 引用键 {env_id, config_type, config_mode}
     （按名称字典反查，多义不猜测）；剔除废弃键 env_name/env_ids/involve_envs/config_name/
     config_host/config_port/database_name（D4 host 快照、D5 环境名快照）；
     重算 task_involve_env_ids，task_involve_envs 由绑定 ID 反查刷新（D5 改名漂移）；
  R4 step.database_operates/redis_operates：config_name → config_mode；DB 的 database_name → config_id
     （按 mode+旧库名在同 mode 配置行中唯一命中才回填，同 mode 多环境库名不同不猜测），
     随后剔除废弃键 config_name/database_name（Redis 的 database_name 为库编号必填，保留）；
  R5 details：request_config_mode 空值仅对 HTTP/TCP 请求步骤回填（优先执行期名称快照反查，
     历史改名不可解析时按步骤当前 mode 兜底）；明细 operates 为独立快照契约
     （index/env_name/config_name/database_name 必填，与步骤定义不同），不在改造范围，不动；
  R6 报告项（不写库）：孤儿 env 字典（D6，读取侧已过滤）、无法解析的引用清单。

安全约定：默认 dry-run 仅打印计划；--apply 单事务执行，写前备份受影响行原始值到
backend/output/legacy_data_backup_{db}_{时间戳}.json；解析不到/多义的引用不猜测，
任务整体排除待人工，明细/步骤按行跳过并列入清单；已修复行跳过（幂等）。

用法（仓库根目录，连接参数缺省读 backend/.env，--host/--port/--user/--password/--database/--prefix 可覆盖）：
    backend/.venv/bin/python -m backend.scripts.repair_legacy_config_data
    backend/.venv/bin/python -m backend.scripts.repair_legacy_config_data --apply
"""
import argparse
import datetime
import json
import os
import re
import sys
import uuid
from collections import defaultdict

import pymysql

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)

_ENV_TYPE_ALIAS = {"app": "app", "database": "database", "db": "database", "redis": "redis", "file": "file"}
_REQUEST_STEP_TYPES = ("HTTP请求", "TCP请求")  # step_type 落库为枚举中文描述
_STEP_DROP_KEYS = ("env_name", "config_name", "config_host", "config_port", "database_name")
_TOP_LEVEL_KEYS = ("env_mode", "env_id")


def _load_env_defaults() -> dict:
    """与工程一致从 backend/.env 读取数据库连接缺省值（KEY=VALUE，忽略注释）。"""
    defaults = {}
    env_path = os.path.join(_BACKEND_DIR, ".env")
    if os.path.isfile(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                defaults[k.strip()] = v.strip().strip('"').strip("'")
    return defaults


def _unique_identify() -> str:
    """与 scaffold.unique_identify 同口径：时间戳-UUID大写。"""
    return f"{int(datetime.datetime.now().timestamp())}-{uuid.uuid4().hex.upper()}"


def _json_load(v):
    if isinstance(v, (bytes, bytearray)):
        v = v.decode("utf-8")
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (ValueError, TypeError):
            return None
    return v


def _norm_type(v) -> str:
    return _ENV_TYPE_ALIAS.get(str(v or "").strip().lower(), "")


def _name_key(v) -> str:
    return str(v or "").strip().lower()


def _detect_prefix(cur, database: str) -> str:
    """按 {prefix}_autotest_task 表自动探测表前缀（krun/tbx 两端通用）。"""
    cur.execute(
        "SELECT TABLE_NAME FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME LIKE '%%\\_autotest\\_task'",
        (database,),
    )
    prefixes = {r["TABLE_NAME"][: -len("_autotest_task")] for r in cur.fetchall()}
    prefixes.discard("")
    if len(prefixes) != 1:
        raise SystemExit(f"[error] 无法唯一确定表前缀，探测结果={sorted(prefixes)}，请用 --prefix 显式指定")
    return prefixes.pop()


class RepairContext:
    def __init__(self, cur, prefix: str):
        self.cur = cur
        self.p = prefix
        self.bind_map = {}          # (project_id, env_type, 环境名小写) -> [绑定ID]（启用绑定）
        self.bind_names = {}        # 绑定ID -> 环境名
        self.config_map = {}        # (project_id, env_type, 配置名小写) -> config_mode（启用配置）
        self.config_map_all = {}    # 同上含软删（明细历史快照解析用）
        self.mode_db_rows = defaultdict(list)  # config_mode -> [(配置行ID, database_name)]（DB operates config_id 回填用）
        self.mode_names = defaultdict(set)     # config_mode -> 配置名集合（多候选报告展示用）
        self.case_projects = {}     # case_id -> project_id
        self.step_modes = {}        # step_id -> request_config_mode（启用步骤）
        self.task_updates = []      # (task_id, {列: 新值})
        self.step_updates = []
        self.detail_updates = []
        self.config_updates = []    # (config_id, {列: 新值})
        self.perf_updates = []
        self.unresolved = []
        self.report_only = []
        self.blocked_tasks = set()
        self.existing_tables = {r["TABLE_NAME"] for r in self.query(
            "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()")}

    def t(self, name: str) -> str:
        return f"{self.p}_{name}"

    def has_table(self, name: str) -> bool:
        """第三方库可能未启用压测等模块，缺表时对应修复项自动降级跳过。"""
        return self.t(name) in self.existing_tables

    def query(self, sql: str, args=None) -> list:
        self.cur.execute(sql, args or ())
        return self.cur.fetchall()

    def columns(self, table: str) -> set:
        rows = self.query(f"SHOW COLUMNS FROM {self.t(table)}")
        return {r["Field"] for r in rows}

    def load_dicts(self):
        # 环境绑定字典：兼容 env_name 直存与 env_enum_id 关联 env 字典两种历史结构
        bind_cols = self.columns("autotest_env_bind")
        if "env_enum_id" in bind_cols:
            binds = self.query(
                f"SELECT b.id, b.project_id, b.env_type, e.env_name "
                f"FROM {self.t('autotest_env_bind')} b "
                f"LEFT JOIN {self.t('autotest_env')} e ON e.id = b.env_enum_id "
                f"WHERE b.state != 1"
            )
        else:
            binds = self.query(
                f"SELECT id, project_id, env_type, env_name FROM {self.t('autotest_env_bind')} WHERE state != 1"
            )
        grouped = defaultdict(list)
        for b in binds:
            et = _norm_type(b["env_type"])
            name = str(b["env_name"] or "").strip()
            if not et or not name:
                continue
            self.bind_names[b["id"]] = name
            grouped[(b["project_id"], et, _name_key(name))].append(b["id"])
        self.bind_map = dict(grouped)
        # 配置名称字典：启用口径供任务/步骤/压测引用，全量口径供明细历史快照
        for c in self.query(
            f"SELECT id, project_id, env_type, config_name, config_mode, database_name, state FROM {self.t('autotest_env_config')}"
        ):
            et = _norm_type(c["env_type"])
            mode = str(c["config_mode"] or "").strip()
            if not et or not mode or not c["project_id"]:
                continue
            key = (c["project_id"], et, _name_key(c["config_name"]))
            self.config_map_all[key] = mode
            self.mode_names[mode].add(str(c["config_name"] or "").strip())
            if c["state"] != 1:
                self.config_map[key] = mode
                if et == "database":
                    self.mode_db_rows[mode].append((c["id"], str(c["database_name"] or "").strip()))
        for c in self.query(f"SELECT id, case_project FROM {self.t('autotest_case')} WHERE state != 1"):
            self.case_projects[c["id"]] = c["case_project"]
        for s in self.query(
            f"SELECT id, request_config_mode FROM {self.t('autotest_step')} "
            f"WHERE state != 1 AND request_config_mode IS NOT NULL AND request_config_mode != ''"
        ):
            self.step_modes[s["id"]] = s["request_config_mode"]
        print(f"[dict] 环境绑定{len(self.bind_names)}个, 配置mode映射{len(self.config_map)}组(全量{len(self.config_map_all)}), "
              f"用例{len(self.case_projects)}个")

    def resolve_bind(self, project_id, env_type: str, env_name: str):
        ids = self.bind_map.get((project_id, _norm_type(env_type), _name_key(env_name))) or []
        if len(ids) == 1:
            return ids[0]
        return None  # 缺失或多义均不猜测

    def resolve_mode(self, project_id, env_type: str, config_name: str, include_deleted=False):
        m = (self.config_map_all if include_deleted else self.config_map).get(
            (project_id, _norm_type(env_type), _name_key(config_name)))
        return m or None


def repair_env_configs(ctx: RepairContext):
    """R1：空mode分组生成 + 冗余维度回填。"""
    rows = ctx.query(
        f"SELECT c.id, c.config_name, c.config_mode, c.project_id, c.env_type, c.env_bind_id, "
        f"b.project_id AS b_project, b.env_type AS b_type "
        f"FROM {ctx.t('autotest_env_config')} c "
        f"LEFT JOIN {ctx.t('autotest_env_bind')} b ON b.id = c.env_bind_id "
        f"WHERE c.state != 1"
    )
    groups = defaultdict(list)
    for r in rows:
        updates = {}
        if not str(r["config_mode"] or "").strip():
            pid = r["project_id"] or r["b_project"]
            et = _norm_type(r["env_type"] or r["b_type"])
            if pid and et:
                groups[(pid, et, _name_key(r["config_name"]))].append(r["id"])
            else:
                ctx.unresolved.append(f"env_config[{r['id']}] 空mode且无法确定应用/节点维度")
        if not r["project_id"] and r["b_project"]:
            updates["project_id"] = r["b_project"]
        if not _norm_type(r["env_type"]) and _norm_type(r["b_type"]):
            updates["env_type"] = _norm_type(r["b_type"])
        if updates:
            ctx.config_updates.append((r["id"], updates))
    for (pid, et, name), ids in groups.items():
        mode = _unique_identify()
        for cid in ids:
            ctx.config_updates.append((cid, {"config_mode": mode}))
        # 同步刷新名称字典，供后续修复项按"已生成"口径解析
        ctx.config_map[(pid, et, name)] = mode
        ctx.config_map_all[(pid, et, name)] = mode
        print(f"[R1] 空mode分组生成: 应用{pid}/{et}/名称[{name}] {len(ids)}行 -> {mode}")


def repair_request_modes_from_name(ctx: RepairContext):
    """R2-a：旧名称列仍在（迁移32未执行）时按名称反查回填 step/perf_api 的 request_config_mode。"""
    for table, extra in (("autotest_step", "AND step_type IN ('HTTP请求','TCP请求')"), ("perf_api", "")):
        if not ctx.has_table(table) or "request_config_name" not in ctx.columns(table):
            continue
        rows = ctx.query(
            f"SELECT id, request_project_id, request_config_name FROM {ctx.t(table)} "
            f"WHERE state != 1 {extra} AND (request_config_mode IS NULL OR request_config_mode = '') "
            f"AND request_config_name IS NOT NULL AND request_config_name != ''"
        )
        for r in rows:
            mode = ctx.resolve_mode(r["request_project_id"], "app", r["request_config_name"])
            if mode:
                if table == "autotest_step":
                    ctx.step_updates.append((r["id"], {"request_config_mode": mode}))
                    ctx.step_modes[r["id"]] = mode
                else:
                    ctx.perf_updates.append((r["id"], {"request_config_mode": mode}))
            else:
                ctx.unresolved.append(f"{table}[{r['id']}] 配置名[{r['request_config_name']}]无法解析mode")


def _repair_operates(ctx: RepairContext, ops, project_id, owner: str, is_redis: bool):
    """步骤定义 operates 引用键化：config_name→config_mode，DB 的 database_name→config_id，
    剔除废弃键；返回 (新列表, 是否变更)。"""
    if isinstance(ops, dict):
        ops = [ops]
    if not isinstance(ops, list):
        return ops, False
    changed = False
    result = []
    for idx, op in enumerate(ops):
        if not isinstance(op, dict):
            result.append(op)
            continue
        op = dict(op)
        if not str(op.get("config_mode") or "").strip():
            name = str(op.get("config_name") or "").strip()
            mode = ctx.resolve_mode(project_id, "redis" if is_redis else "database", name) if name else None
            if mode:
                op["config_mode"] = mode
                changed = True
            else:
                ctx.unresolved.append(f"{owner} operates[{idx}] 配置名[{name or '空'}]无法解析mode")
        if not is_redis:
            # database_name → config_id：同 mode 多环境实例库名可能不同，按旧库名唯一命中才回填（展示引用，可选）
            if not op.get("config_id") and str(op.get("config_mode") or "").strip():
                old_db = str(op.get("database_name") or "").strip()
                hits = [cid for cid, db in ctx.mode_db_rows.get(op["config_mode"], []) if old_db and db == old_db]
                if len(hits) == 1:
                    op["config_id"] = hits[0]
                    changed = True
        for key in ("config_name",) + (() if is_redis else ("database_name",)):
            if key in op:
                op.pop(key)
                changed = True
        result.append(op)
    return result, changed


def repair_tasks(ctx: RepairContext):
    """R3：任务 cases_execute_config 引用键化 + 废弃键剔除 + involve_ids/envs 重算刷新。"""
    rows = ctx.query(
        f"SELECT id, task_project, cases_execute_config, task_involve_env_ids, task_involve_envs "
        f"FROM {ctx.t('autotest_task')}"
    )
    for row in rows:
        cfg = _json_load(row["cases_execute_config"])
        if not isinstance(cfg, dict) or not cfg:
            continue
        task_id, project_id = row["id"], row["task_project"]
        new_cfg, changed, blocked = {}, False, False
        env_ids = set()
        for case_key, case_cfg in cfg.items():
            if case_key in _TOP_LEVEL_KEYS:
                new_cfg[case_key] = case_cfg
                continue
            if not str(case_key).isdigit() or not isinstance(case_cfg, dict):
                changed = True  # 废弃顶层键（env_name/env_ids等）与非用例键一律剔除
                continue
            case_cfg = dict(case_cfg)
            steps = case_cfg.get("steps_execute_config") or {}
            new_steps = {}
            case_env_ids = set()
            for step_key, step_cfg in steps.items():
                if not isinstance(step_cfg, dict):
                    new_steps[step_key] = step_cfg
                    continue
                step_cfg = dict(step_cfg)
                if all(step_cfg.get(k) for k in ("env_id", "config_type", "config_mode")):
                    new_steps[step_key] = {k: step_cfg[k] for k in ("env_id", "config_type", "config_mode")}
                    if new_steps[step_key] != step_cfg:
                        changed = True
                    case_env_ids.add(int(step_cfg["env_id"]))
                    continue
                env_name = str(step_cfg.get("env_name") or "").strip()
                config_name = str(step_cfg.get("config_name") or "").strip()
                env_type = _norm_type(step_cfg.get("config_type"))
                bind_id = ctx.resolve_bind(project_id, env_type, env_name) if env_name else None
                mode = ctx.resolve_mode(project_id, env_type, config_name) if config_name else None
                if bind_id and mode and env_type:
                    new_steps[step_key] = {"env_id": bind_id, "config_type": env_type, "config_mode": mode}
                    case_env_ids.add(bind_id)
                    changed = True
                else:
                    ctx.unresolved.append(
                        f"task[{task_id}] case[{case_key}] step[{step_key}] "
                        f"环境[{env_name or '空'}]/配置[{config_name or '空'}]无法解析")
                    blocked = True
                    new_steps[step_key] = step_cfg
            if blocked:
                ctx.blocked_tasks.add(task_id)
            new_case = {"execute_count": case_cfg.get("execute_count", 1),
                        "involve_env_ids": sorted(case_env_ids),
                        "steps_execute_config": new_steps}
            if new_case != case_cfg:
                changed = True
            new_cfg[case_key] = new_case
            env_ids |= case_env_ids
        if task_id in ctx.blocked_tasks:
            continue  # 含无法解析引用的任务整体不写入，原值保留待人工处理后重跑
        updates = {}
        if changed:
            updates["cases_execute_config"] = new_cfg
        # involve_ids：NULL/空则重算；已有值与配置不一致也以配置为准刷新
        ids_sorted = sorted(env_ids)
        old_ids = _json_load(row["task_involve_env_ids"])
        if ids_sorted and old_ids != ids_sorted:
            updates["task_involve_env_ids"] = ids_sorted
        # involve_envs 名称快照：由绑定ID反查刷新（D5 环境改名漂移）
        names = sorted({ctx.bind_names[i] for i in (updates.get("task_involve_env_ids") or old_ids or []) if i in ctx.bind_names})
        old_names = _json_load(row["task_involve_envs"])
        if names and old_names != names:
            updates["task_involve_envs"] = names
        if updates:
            ctx.task_updates.append((task_id, updates))


def repair_step_operates(ctx: RepairContext):
    """R4：步骤 operates 引用键化。"""
    rows = ctx.query(
        f"SELECT s.id, c.case_project AS project_id, s.database_operates, s.redis_operates "
        f"FROM {ctx.t('autotest_step')} s "
        f"LEFT JOIN {ctx.t('autotest_case')} c ON c.id = s.case_id WHERE s.state != 1"
    )
    pending = {sid: dict(u) for sid, u in ctx.step_updates}
    for row in rows:
        updates = pending.get(row["id"], {})
        for col, is_redis in (("database_operates", False), ("redis_operates", True)):
            ops = _json_load(row[col])
            if not ops:
                continue
            new_ops, changed = _repair_operates(ctx, ops, row["project_id"], f"step[{row['id']}].{col}", is_redis)
            if changed:
                updates[col] = new_ops
        if updates:
            if row["id"] in pending:
                idx = next(i for i, (sid, _) in enumerate(ctx.step_updates) if sid == row["id"])
                ctx.step_updates[idx] = (row["id"], updates)
            else:
                ctx.step_updates.append((row["id"], updates))


def repair_step_modes_from_refs(ctx: RepairContext):
    """R2-b：空mode步骤从任务配置/明细快照恢复（候选唯一才写）；名称列仍在时 R2-a 已按名称处理，
    本项兼顾名称也为空的残留步骤，两项均只处理空mode行不冲突。"""
    candidates = defaultdict(set)      # 明细快照候选（次级）
    task_candidates = defaultdict(set)  # 任务保存快照候选（权威，任务保存后即为执行期权威）
    # 全量任务（含已是新结构无变更的）；本次计划回填的任务优先采用计划内新结构（库内旧结构尚无config_mode）
    planned_cfg = {tid: u["cases_execute_config"] for tid, u in ctx.task_updates if "cases_execute_config" in u}
    for t in ctx.query(f"SELECT id, cases_execute_config FROM {ctx.t('autotest_task')}"):
        cfg = planned_cfg.get(t["id"]) or _json_load(t["cases_execute_config"])
        if not isinstance(cfg, dict):
            continue
        for case_key, case_cfg in cfg.items():
            if case_key in _TOP_LEVEL_KEYS or not isinstance(case_cfg, dict):
                continue
            for step_key, step_cfg in (case_cfg.get("steps_execute_config") or {}).items():
                if str(step_key).isdigit() and isinstance(step_cfg, dict) and _norm_type(step_cfg.get("config_type")) == "app":
                    task_candidates[int(step_key)].add(step_cfg.get("config_mode"))
    for d in ctx.query(
        f"SELECT step_id, request_config_mode FROM {ctx.t('autotest_details')} "
        f"WHERE request_config_mode IS NOT NULL AND request_config_mode != ''"
    ):
        candidates[d["step_id"]].add(d["request_config_mode"])
    # 明细 mode 也空时，其执行期名称快照反查配置字典同样可作候选（含软删配置）
    for d in ctx.query(
        f"SELECT step_id, case_id, request_project_id, request_config_name FROM {ctx.t('autotest_details')} "
        f"WHERE (request_config_mode IS NULL OR request_config_mode = '') "
        f"AND step_type IN ('HTTP请求','TCP请求') AND request_config_name IS NOT NULL AND request_config_name != ''"
    ):
        pid = d["request_project_id"] or ctx.case_projects.get(d["case_id"])
        mode = ctx.resolve_mode(pid, "app", d["request_config_name"], include_deleted=True) if pid else None
        if mode:
            candidates[d["step_id"]].add(mode)
    rows = ctx.query(
        f"SELECT id, step_name FROM {ctx.t('autotest_step')} WHERE state != 1 AND step_type IN ('HTTP请求','TCP请求') "
        f"AND (request_config_mode IS NULL OR request_config_mode = '')"
    )
    pending = {sid for sid, _ in ctx.step_updates}
    for row in rows:
        if row["id"] in pending:
            continue
        # 任务保存快照为权威来源：唯一即采用；多义/缺失时才回落明细快照候选
        modes = {m for m in task_candidates.get(row["id"], set()) if m}
        if len(modes) != 1:
            modes = {m for m in candidates.get(row["id"], set()) if m}
        label = f"step[{row['id']}][{row['step_name']}]"
        if len(modes) == 1:
            mode = modes.pop()
            ctx.step_updates.append((row["id"], {"request_config_mode": mode}))
            ctx.step_modes[row["id"]] = mode
        elif not modes:
            ctx.report_only.append(f"{label} request_config_mode为空且无历史绑定(不在任务快照/明细无可用来源)，需编辑页选择配置")
        else:
            names = sorted({n for m in modes for n in ctx.mode_names.get(m, set()) if n})
            ctx.report_only.append(f"{label} request_config_mode为空，候选{len(modes)}个[{'/'.join(names) or '未知名称'}]多义不猜测，需编辑页重选")


def repair_details(ctx: RepairContext):
    """R5：明细 request_config_mode 回填（仅HTTP/TCP请求步骤，其余步骤无请求配置概念）：
    优先执行期名称快照反查（含软删配置），历史名称已改名不可解析时按步骤当前 mode 兜底。
    明细 operates 为独立快照契约（config_name/database_name 必填），存量已符合，不修改。"""
    rows = ctx.query(
        f"SELECT id, case_id, step_id, step_type, request_project_id, request_config_name, request_config_mode "
        f"FROM {ctx.t('autotest_details')} "
        f"WHERE (request_config_mode IS NULL OR request_config_mode = '') AND step_type IN ('HTTP请求','TCP请求')"
    )
    skipped_mode = 0
    for row in rows:
        project_id = row["request_project_id"] or ctx.case_projects.get(row["case_id"])
        name = str(row["request_config_name"] or "").strip()
        mode = ctx.resolve_mode(project_id, "app", name, include_deleted=True) if name and project_id else None
        if not mode:
            mode = ctx.step_modes.get(row["step_id"])  # 名称快照缺失/历史改名时按步骤当前mode兜底
        if mode:
            ctx.detail_updates.append((row["id"], {"request_config_mode": mode}))
        else:
            skipped_mode += 1
    if skipped_mode:
        ctx.report_only.append(f"details request_config_mode无法回填: {skipped_mode}行(名称快照缺失/配置已不可解析，仅影响展示)")


def report_orphans(ctx: RepairContext):
    """R6：孤儿env字典与压测空mode仅报告（读取侧已过滤/无名称来源，不写库）。"""
    bind_cols = ctx.columns("autotest_env_bind")
    if "env_enum_id" in bind_cols:
        orphans = ctx.query(
            f"SELECT e.id, e.env_name FROM {ctx.t('autotest_env')} e "
            f"WHERE NOT EXISTS (SELECT 1 FROM {ctx.t('autotest_env_bind')} b WHERE b.env_enum_id = e.id)"
        )
        for o in orphans:
            ctx.report_only.append(f"孤儿env字典[{o['id']}][{o['env_name']}] 无任何绑定引用(D6读取侧已过滤，无需处理)")
    if ctx.has_table("perf_api") and "request_config_name" not in ctx.columns("perf_api"):
        for r in ctx.query(
            f"SELECT id, api_name FROM {ctx.t('perf_api')} WHERE state != 1 "
            f"AND (request_config_mode IS NULL OR request_config_mode = '')"
        ):
            ctx.report_only.append(f"perf_api[{r['id']}][{r['api_name']}] request_config_mode为空且名称列已删，需编辑页重选")


def validate_repairs(ctx: RepairContext):
    """--apply 落库前用工程 schema 做模型级校验；工程不可导入时降级结构自检。"""
    try:
        if _REPO_ROOT not in sys.path:
            sys.path.insert(0, _REPO_ROOT)
        from backend.applications.autotest.schemas.autotest_task_schema import (
            AutoTestTaskCreate, AutoTestTaskCasesExecuteConfig)
        from backend.applications.autotest.schemas import autotest_step_schema
    except ImportError:
        AutoTestTaskCreate = None
    if AutoTestTaskCreate is not None:
        task_rows = {r["id"]: r for r in ctx.query(f"SELECT * FROM {ctx.t('autotest_task')}")}
        for task_id, updates in ctx.task_updates:
            row = task_rows[task_id]
            merged = dict(row)
            merged.update(updates)
            # 先校验本次修复的核心结构（不受无关存量字段干扰）
            AutoTestTaskCasesExecuteConfig.model_validate(_json_load(merged["cases_execute_config"]))
            # 再按创建入参契约整体校验：列名映射 + JSON字符串列解析
            payload = {k: v for k, v in merged.items() if k in AutoTestTaskCreate.model_fields}
            payload["task_project"] = merged.get("task_project")
            for col in ("task_case_ids", "task_kwargs", "task_notify", "task_notifier", "task_schedule_expr"):
                if col in payload:
                    payload[col] = _json_load(payload[col])
            AutoTestTaskCreate.model_validate(payload)
        for _, updates in ctx.step_updates:
            for op in updates.get("database_operates") or []:
                autotest_step_schema.DataBaseOperates.model_validate(op)
            for op in updates.get("redis_operates") or []:
                autotest_step_schema.RedisOperates.model_validate(op)
        print(f"[validate] 模型级校验通过: 任务{len(ctx.task_updates)}个, "
              f"步骤{len(ctx.step_updates)}行, 明细mode回填{len(ctx.detail_updates)}行")
        return
    # 结构自检兜底：引用键三要素齐全且取值合法
    for task_id, updates in ctx.task_updates:
        for case_key, case_cfg in (updates.get("cases_execute_config") or {}).items():
            if case_key in _TOP_LEVEL_KEYS:
                continue
            assert str(case_key).isdigit(), f"task[{task_id}] 非法用例键{case_key}"
            for step_key, step_cfg in (case_cfg.get("steps_execute_config") or {}).items():
                assert isinstance(step_cfg.get("env_id"), int) and step_cfg["env_id"] >= 1, f"task[{task_id}].{step_key} env_id非法"
                assert _norm_type(step_cfg.get("config_type")), f"task[{task_id}].{step_key} config_type非法"
                mode = step_cfg.get("config_mode")
                assert isinstance(mode, str) and 0 < len(mode) <= 64, f"task[{task_id}].{step_key} config_mode非法"
    for owner, updates in ctx.step_updates:
        for col in ("database_operates", "redis_operates"):
            for idx, op in enumerate(updates.get(col) or []):
                mode = op.get("config_mode")
                assert isinstance(mode, str) and 0 < len(mode) <= 64, f"{owner} {col}[{idx}] config_mode非法"
    print(f"[validate] 结构自检通过: 任务{len(ctx.task_updates)}个, 步骤{len(ctx.step_updates)}行, 明细mode回填{len(ctx.detail_updates)}行")


def apply_updates(ctx: RepairContext, database: str):
    """写前备份受影响行原始值，随后单事务写入。"""
    stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    backup = {"database": database, "time": stamp, "tables": {}}
    plans = (
        ("autotest_task", ctx.task_updates),
        ("autotest_step", ctx.step_updates),
        ("autotest_details", ctx.detail_updates),
        ("autotest_env_config", ctx.config_updates),
        ("perf_api", ctx.perf_updates),
    )
    plans = tuple((table, updates) for table, updates in plans if updates and ctx.has_table(table))
    for table, updates in plans:
        if not updates:
            continue
        ids = [rid for rid, _ in updates]
        marks = ",".join(["%s"] * len(ids))
        backup["tables"][table] = ctx.query(f"SELECT * FROM {ctx.t(table)} WHERE id IN ({marks})", ids)
    os.makedirs(os.path.join(_BACKEND_DIR, "output"), exist_ok=True)
    backup_path = os.path.join(_BACKEND_DIR, "output", f"legacy_data_backup_{database}_{stamp}.json")
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=1, default=str)
    print(f"[backup] 原始值已备份: {backup_path}")
    total = 0
    for table, updates in plans:
        for rid, values in updates:
            sets = ", ".join(f"`{col}`=%s" for col in values)
            args = [json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for v in values.values()]
            ctx.cur.execute(f"UPDATE {ctx.t(table)} SET {sets} WHERE id=%s", (*args, rid))
            total += 1
    ctx.cur.connection.commit()
    print(f"[apply] 单事务写入完成: 共{total}行")


def main():
    defaults = _load_env_defaults()
    parser = argparse.ArgumentParser(description="配置名称绑定改造存量数据纠正（krun/tbx 两端通用）")
    parser.add_argument("--host", default=defaults.get("DATABASE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(defaults.get("DATABASE_PORT", "3306")))
    parser.add_argument("--user", default=defaults.get("DATABASE_USERNAME", "root"))
    parser.add_argument("--password", default=defaults.get("DATABASE_PASSWORD", ""))
    parser.add_argument("--database", default=defaults.get("DATABASE_NAME", "krun"))
    parser.add_argument("--prefix", default=None, help="表前缀（缺省按 {prefix}_autotest_task 自动探测）")
    parser.add_argument("--apply", action="store_true", help="实际写入（缺省仅dry-run报告）")
    args = parser.parse_args()

    conn = pymysql.connect(host=args.host, port=args.port, user=args.user, password=args.password,
                           database=args.database, charset="utf8mb4", autocommit=False)
    cur = conn.cursor(pymysql.cursors.DictCursor)
    prefix = args.prefix or _detect_prefix(cur, args.database)
    print(f"[target] {args.host}:{args.port}/{args.database} 表前缀={prefix}_ 模式={'APPLY' if args.apply else 'DRY-RUN'}")
    ctx = RepairContext(cur, prefix)
    ctx.load_dicts()

    repair_env_configs(ctx)
    repair_request_modes_from_name(ctx)
    repair_tasks(ctx)
    repair_step_operates(ctx)
    repair_step_modes_from_refs(ctx)
    repair_details(ctx)
    report_orphans(ctx)

    print("\n=== 修复计划 ===")
    print(f"R1 环境配置(mode生成/维度回填): {len(ctx.config_updates)}行 {[i for i, _ in ctx.config_updates]}")
    print(f"R2/R4 步骤(mode恢复/operates键化): {len(ctx.step_updates)}行 {[i for i, _ in ctx.step_updates]}")
    print(f"R3 任务(引用键化/involve重算): {len(ctx.task_updates)}行 {[i for i, _ in ctx.task_updates]}")
    print(f"R5 明细(mode回填): {len(ctx.detail_updates)}行")
    print(f"R2 压测接口mode回填: {len(ctx.perf_updates)}行 {[i for i, _ in ctx.perf_updates]}")
    if ctx.blocked_tasks:
        print(f"[blocked] 含无法解析引用整体排除的任务: {sorted(ctx.blocked_tasks)}（人工处理后重跑）")
    if ctx.unresolved:
        print(f"\n=== 无法解析清单({len(ctx.unresolved)}项，不猜测) ===")
        agg = defaultdict(int)
        for item in ctx.unresolved:
            agg[re.sub(r"\[\d+\]", "[*]", item)] += 1
        for item, cnt in sorted(agg.items(), key=lambda kv: -kv[1]):
            print(f" - {item}" + (f" ×{cnt}" if cnt > 1 else ""))
    if ctx.report_only:
        # 逐行诊断清单：保留真实ID/名称/候选，不聚合不截断，供人工逐项处理
        print(f"\n=== 仅报告项({len(ctx.report_only)}) ===")
        for item in ctx.report_only:
            print(f" - {item}")

    has_work = any((ctx.task_updates, ctx.step_updates, ctx.detail_updates, ctx.config_updates, ctx.perf_updates))
    if not has_work:
        print("\n[ok] 无可修复项，存量数据已符合新结构")
        conn.close()
        return 0
    if not args.apply:
        print("\n[dry-run] 未写入任何数据；确认计划后追加 --apply 执行")
        conn.close()
        return 0
    validate_repairs(ctx)
    apply_updates(ctx, args.database)
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
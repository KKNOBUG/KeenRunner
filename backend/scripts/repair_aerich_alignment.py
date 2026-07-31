# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : scripts/repair_aerich_alignment
@DateTime: 2026/7/31

修复 aerich 迁移记录与迁移文件错位问题。

背景:
    aerich 计算"下一个迁移序号"的规则是: aerich表中 id 最大的记录(Meta.ordering=["-id"])的版本号 + 1。
    手工迁移文件复用序号(如 10_20260730_xxx)或表记录缺失, 会导致新迁移与历史文件撞号,
    弹出 "Miration file exists(...). Do you want to remove it?" 提示。

修复动作(幂等, 默认 dry-run 只打印不改动):
    1. 删除 aerich 表中的"残留记录"(数据库有记录但磁盘无对应文件, 如已删除的手工迁移);
    2. 补登"缺失记录"(磁盘有文件但 aerich 表无记录 —— DDL 实际已生效, 仅补登记不执行SQL);
    3. 调用 aerich Command.upgrade 真实应用剩余未记录的迁移文件(如本次新增的 40 号);
    4. 校验修复结果: aerich 表记录与磁盘文件一一对应, 且 id 最大记录为最高版本号。

用法:
    backend/.venv/bin/python backend/scripts/repair_aerich_alignment.py            # dry-run
    backend/.venv/bin/python backend/scripts/repair_aerich_alignment.py --execute  # 实际执行
"""
import argparse
import asyncio
import sys
from pathlib import Path

import aiomysql
from dotenv import dotenv_values

BACKEND_DIR: Path = Path(__file__).resolve().parent.parent
MIGRATION_DIR: Path = BACKEND_DIR / "migrations" / "models"
APP_LABEL: str = "models"
# 补登记录的占位 content；migrate 的 diff 只读取 id 最大记录的 content，补齐后该记录由真实 upgrade 写入，占位永不生效
FAKE_CONTENT: str = "{}"
# 本次新增、需要真实执行 SQL 的迁移文件版本号(小于等于该号的缺失记录仅补登；大于该号的由 upgrade 真实应用)
FAKE_APPLY_MAX_NUM: int = 39


def list_migration_files() -> list[tuple[int, str]]:
    """列出磁盘迁移文件，按版本号升序。"""
    out: list[tuple[int, str]] = []
    for file in MIGRATION_DIR.glob("*.py"):
        num_str: str = file.name.split("_")[0]
        if num_str.isdigit():
            out.append((int(num_str), file.name))
    return sorted(out)


async def repair(execute: bool) -> None:
    cfg = dotenv_values(BACKEND_DIR / ".env")
    conn = await aiomysql.connect(
        host=cfg["DATABASE_HOST"],
        port=int(cfg["DATABASE_PORT"]),
        user=cfg["DATABASE_USERNAME"],
        password=cfg["DATABASE_PASSWORD"],
        db=cfg["DATABASE_NAME"],
        connect_timeout=5,
    )
    try:
        files: list[tuple[int, str]] = list_migration_files()
        file_names: set[str] = {name for _, name in files}
        async with conn.cursor() as cur:
            await cur.execute("SELECT id, version FROM aerich WHERE app=%s ORDER BY id", (APP_LABEL,))
            rows: list[tuple[int, str]] = await cur.fetchall()

            recorded: dict[str, int] = {version: row_id for row_id, version in rows}
            stale_rows: list[tuple[int, str]] = [(row_id, v) for row_id, v in rows if v not in file_names]
            missing_files: list[tuple[int, str]] = [(num, name) for num, name in files if name not in recorded]

            print(f"aerich表记录数: {len(rows)}; 磁盘迁移文件数: {len(files)}")
            print(f"[残留记录](DB有记录/磁盘无文件, 将删除): {len(stale_rows)}")
            for row_id, v in stale_rows:
                print(f"    - id={row_id} version={v}")
            print(f"[缺失记录](磁盘有文件/DB无记录): {len(missing_files)}")
            for num, name in missing_files:
                action = "仅补登(不执行SQL)" if num <= FAKE_APPLY_MAX_NUM else "真实应用(执行SQL)"
                print(f"    - {name} -> {action}")

            if not execute:
                print("\n当前为 dry-run 模式, 未做任何改动; 确认无误后追加 --execute 执行。")
                return

            for row_id, v in stale_rows:
                await cur.execute("DELETE FROM aerich WHERE id=%s", (row_id,))
                print(f"已删除残留记录: id={row_id} version={v}")

            for num, name in missing_files:
                if num > FAKE_APPLY_MAX_NUM:
                    continue
                await cur.execute(
                    "INSERT INTO aerich (version, app, content) VALUES (%s, %s, %s)",
                    (name, APP_LABEL, FAKE_CONTENT),
                )
                print(f"已补登记录: {name}")
        await conn.commit()
    finally:
        conn.close()

    # 真实应用剩余未记录的迁移文件(版本号>FAKE_APPLY_MAX_NUM), 由 aerich 自身执行并登记(含真实 models 快照)
    pending_real: list[str] = [name for num, name in missing_files if num > FAKE_APPLY_MAX_NUM]
    if pending_real:
        print(f"\n调用 aerich upgrade 真实应用: {pending_real}")
        sys.path.insert(0, str(BACKEND_DIR.parent))
        from aerich import Command
        from backend.configure import PROJECT_CONFIG

        config = {
            "connections": PROJECT_CONFIG.DATABASE_CONNECTIONS,
            "apps": {
                "models": {
                    "models": PROJECT_CONFIG.APPLICATIONS_MODELS,
                    "default_connection": "default",
                }
            },
            "use_tz": False,
            "timezone": "Asia/Shanghai",
        }
        command = Command(app=APP_LABEL, tortoise_config=config, location=str(MIGRATION_DIR.parent))
        await command.init()
        migrated: list[str] = await command.upgrade()
        await command.close()
        print(f"aerich upgrade 完成, 应用文件: {migrated}")

    # 校验: 记录与文件一一对应, 且 id 最大记录为最高版本号
    conn = await aiomysql.connect(
        host=cfg["DATABASE_HOST"], port=int(cfg["DATABASE_PORT"]),
        user=cfg["DATABASE_USERNAME"], password=cfg["DATABASE_PASSWORD"],
        db=cfg["DATABASE_NAME"], connect_timeout=5,
    )
    try:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id, version FROM aerich WHERE app=%s ORDER BY id DESC LIMIT 1", (APP_LABEL,))
            last = await cur.fetchone()
            await cur.execute("SELECT COUNT(*) FROM aerich WHERE app=%s", (APP_LABEL,))
            total = (await cur.fetchone())[0]
        final_files: set[str] = {name for _, name in list_migration_files()}
        print(f"\n[校验] aerich表记录数: {total}; 磁盘文件数: {len(final_files)}; id最大记录: {last}")
        if last and int(last[1].split("_")[0]) == max(num for num, _ in list_migration_files()):
            print("[校验] 通过: 最新记录与最高版本文件一致, 后续 aerich migrate 将生成下一个序号, 不再撞号。")
        else:
            print("[校验] 警告: 最新记录与最高版本文件不一致, 请人工核查!")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="修复 aerich 迁移记录与迁移文件错位")
    parser.add_argument("--execute", action="store_true", help="实际执行修复(默认 dry-run 只打印)")
    args = parser.parse_args()
    asyncio.run(repair(execute=args.execute))
    # 最终在项目根目录执行命令： .venv/bin/python scripts/repair_aerich_alignment.py --execute

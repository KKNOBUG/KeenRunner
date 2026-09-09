# -*- coding: utf-8 -*-
"""
修复 aerich 迁移登记与迁移文件对不上的通用工具。

背景:
    数据库(aerich表)记录了"哪些迁移文件已经被执行过";
    数据库(aerich表)中最新的一条记录存的是"上次迁移时模型长什么样";
    aerich 生成新迁移时不看数据库真实结构, 只对比快照和当前模型的差异。
    数据库(aerich表)记录一旦和磁盘上的迁移文件对不上(如：漏记、多记、重复记), 就会出两类问题:
        1.轻则：新迁移文件序号和已有文件重复, 生产启动时卡住等人确认处理;
        2.重则：快照错乱, 下次迁移误以为数据库是空的, 生成一整套建表SQL甚至错误的SQL。

能力:
    1. 去除重复: 同一个迁移文件被数据库记了多次时, 只保留最后记的那条;
    2. 删除残留: 数据库存在记录、但磁盘上迁移文件不存在, 则删掉这条记录;
    3. 查漏补缺: 磁盘上有迁移文件但数据库没记录, 序号在查漏补缺范围内的只在aerich表补一条记录(不改业务表结构), 超过范围的真实执行文件里的SQL(会改表结构);
    4. 重建基线: 数据库最新记录的快照为空时, 用当前模型重新生成一份, 防止下次迁移生成全量建表SQL;
    5. 迁移预览: 计算出下次迁移会执行哪些SQL并打印, 提前发现删字段、改字段名可能丢数据的问题;
    6. 结果校验: 检查数据库和磁盘上的迁移文件是否一一对应, 有问题会明确报告。

边界:
    - 它只修"aerich表记录", 数据库真实结构和代码模型对不上的问题无法发现和修复;
    - 已经被误删的字段数据无法找回;
    - 应用(gunicorn多个进程)同时在跑迁移会互相冲突, 修复期间请先停掉应用。

用法(在项目根目录执行):
    .venv/bin/python scripts/repair_aerich_alignment.py
"""
import asyncio
import os
import sys
from pathlib import Path

import aiomysql
from dotenv import dotenv_values

BACKEND_DIR: Path = Path(__file__).resolve().parent.parent
MIGRATION_DIR: Path = BACKEND_DIR / "migrations" / "models"
# 查漏补缺时数据库用的空快照(若它恰好成为数据库最新一条, 下次迁移会误以为数据库是空的, 需菜单[3]重建)
FAKE_CONTENT: str = "{}"
# 查漏补缺范围填all时用的上限值, 效果是所有漏记文件都只补记录、不执行SQL
FAKE_MAX_ALL: int = 10 ** 9
# 数据库锁的名字前缀, 防止两个人同时跑修复; 程序退出后锁自动释放
LOCK_KEY_PREFIX: str = "aerich_repair"
# 菜单默认使用的应用名和查漏补缺范围
DEFAULT_APP: str = "models"
DEFAULT_FAKE_MAX: str = "auto"


def list_migration_files() -> list[tuple[int, str]]:
    """按序号从小到大列出磁盘上的迁移文件名。"""
    out: list[tuple[int, str]] = []
    for file in MIGRATION_DIR.glob("*.py"):
        num_str: str = file.name.split("_")[0]
        if num_str.isdigit():
            out.append((int(num_str), file.name))
    return sorted(out)


def find_duplicate_records(rows: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """找出被记了多次的文件记录(每个文件保留最后写入的一条, 其余都算重复)。"""
    latest_id_by_version: dict[str, int] = {}
    for row_id, version in rows:
        latest_id_by_version[version] = max(latest_id_by_version.get(version, 0), row_id)
    return [(row_id, version) for row_id, version in rows if row_id != latest_id_by_version[version]]


def resolve_fake_max(raw: str, matched_max_num: int | None) -> int:
    """
    把输入的查漏补缺范围换算成具体序号。

    auto=数据库已记到的最大序号(一条都没记过按-1算, 等于全部真实执行);
    all=全部只补记录;
    数字=就用这个序号。
    """
    if raw == "all":
        return FAKE_MAX_ALL
    if raw == "auto":
        return matched_max_num if matched_max_num is not None else -1
    return int(raw)


def print_repair_plan(
        duplicate_rows: list[tuple[int, str]],
        stale_rows: list[tuple[int, str]],
        missing_files: list[tuple[int, str]],
        fake_max: int,
) -> None:
    """打印修复清单: 哪些记录要删、哪些文件要补、分别怎么处理。"""
    print(f"[登记修复] 重复记录(同一个迁移文件被记了多次, 保留最后一条, 其余删除): {len(duplicate_rows)} 条")
    for row_id, version in duplicate_rows:
        print(f"    - id={row_id} {version}")
    print(f"[登记修复] 无效记录(数据库中有记录, 但磁盘迁移文件已不在, 记录将删除): {len(stale_rows)} 条")
    for row_id, version in stale_rows:
        print(f"    - id={row_id} {version}")
    print(f"[登记修复] 查漏补缺(磁盘上有迁移文件, 但是数据库没有记录): {len(missing_files)} 个")
    for num, name in missing_files:
        action = "只补记录(不执行SQL、不改业务表结构)" if num <= fake_max else "真实应用(执行SQL、改业务表结构)"
        print(f"    - {name} -> {action}")
    if any(num > fake_max for num, _ in missing_files):
        print("[提示] 标记为\"真实应用\"的文件会真的修改业务表结构; 如果这些SQL其实早就执行过,")
        print("       真跑会报\"列已存在\"这类错误, 届时把查漏补缺范围改成<已执行过的最大序号>重跑即可。")


async def open_db_connection() -> aiomysql.Connection:
    """读取.env里的数据库配置, 创建一个数据库连接。"""
    cfg = dotenv_values(BACKEND_DIR / ".env")
    required_keys = ("DATABASE_HOST", "DATABASE_PORT", "DATABASE_USERNAME", "DATABASE_PASSWORD", "DATABASE_NAME")
    missing_keys = [key for key in required_keys if not cfg.get(key)]
    if missing_keys:
        raise RuntimeError(f".env缺少数据库配置项: {missing_keys}")
    return await aiomysql.connect(
        host=cfg["DATABASE_HOST"],
        port=int(cfg["DATABASE_PORT"]),
        user=cfg["DATABASE_USERNAME"],
        password=cfg["DATABASE_PASSWORD"],
        db=cfg["DATABASE_NAME"],
        connect_timeout=5,
    )


def ensure_project_import() -> None:
    """把项目根目录加到模块搜索路径里, 保证在任意目录下都能导入项目代码。"""
    root = str(BACKEND_DIR)
    if root not in sys.path:
        sys.path.insert(0, root)


def build_tortoise_config(project_config, app: str) -> dict:
    """拼出和项目启动时一样的数据库配置, 保证这里的迁移行为和应用保持一致。"""
    return {
        "connections": project_config.DATABASE_CONNECTIONS,
        "apps": {
            app: {
                "models": project_config.APPLICATIONS_MODELS,
                "default_connection": "default",
            }
        },
        "use_tz": False,
        "timezone": "Asia/Shanghai",
    }


async def repair_records(app: str, fake_max: str, execute: bool, assume_yes: bool) -> tuple[list[tuple[int, str]], int]:
    """核对并修复aerich表记录(去重/删无效/查漏补缺), 加数据库锁防止两个人同时修。

    execute为False时只看不改; assume_yes为False时列出清单后需要手动确认。
    返回(需要真实执行SQL的漏记文件, 本次打算修改的条数)。
    """
    files = list_migration_files()
    file_names: set[str] = {name for _, name in files}
    conn = await open_db_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute("SELECT GET_LOCK(%s, 0)", (f"{LOCK_KEY_PREFIX}_{app}",))
            if (await cur.fetchone())[0] != 1:
                print(f"[登记修复] 另一个修复正在运行(锁 {LOCK_KEY_PREFIX}_{app} 被占用), 请等它结束后再试。")
                sys.exit(1)
            await cur.execute("SELECT id, version FROM aerich WHERE app=%s ORDER BY id", (app,))
            rows: list[tuple[int, str]] = await cur.fetchall()

            duplicate_rows = find_duplicate_records(rows)
            duplicate_ids = {row_id for row_id, _ in duplicate_rows}
            effective_rows = [(row_id, version) for row_id, version in rows if row_id not in duplicate_ids]
            recorded: dict[str, int] = {version: row_id for row_id, version in effective_rows}
            stale_rows = [(row_id, version) for row_id, version in effective_rows if version not in file_names]
            missing_files = [(num, name) for num, name in files if name not in recorded]
            matched_max_num = max((num for num, name in files if name in recorded), default=None)
            resolved_fake_max = resolve_fake_max(fake_max, matched_max_num)
            pending_real = [(num, name) for num, name in missing_files if num > resolved_fake_max]
            planned_changes = len(duplicate_rows) + len(stale_rows) + len(missing_files)

            fake_max_text = "all" if resolved_fake_max >= FAKE_MAX_ALL else str(resolved_fake_max)
            print(f"[登记修复] 迁移文件目录: {MIGRATION_DIR}")
            print(
                f"[登记修复] 数据库中记录 {len(rows)} 条(重复 {len(duplicate_rows)} 条); 磁盘迁移文件 {len(files)} 个; 查漏补缺范围: {fake_max_text}")
            print_repair_plan(duplicate_rows, stale_rows, missing_files, resolved_fake_max)
            if matched_max_num is None and missing_files:
                print("[提示] 数据库里没有一条记录和磁盘文件对得上, 查漏补缺范围自动按 -1 处理: 所有漏记文件都会真实执行SQL!")
                print("       如果这些SQL其实早就执行过, 请在查漏补缺范围处输入all(只补记录, 不执行SQL)。")

            if not execute:
                print("\n[体检] 以上是只读分析, 没有改动任何数据; 需要修复时选择菜单[2]。")
                return pending_real, planned_changes
            if not assume_yes:
                if planned_changes == 0:
                    print("[登记修复] 数据库和文件本来就是对齐的, 不需要修复。")
                    return pending_real, 0
                if not confirm("确认按上面的清单修复数据库?"):
                    print("[登记修复] 已取消, 没有改动。")
                    return pending_real, 0

            for row_id, version in duplicate_rows:
                await cur.execute("DELETE FROM aerich WHERE id=%s", (row_id,))
                print(f"[登记修复] 已删除重复记录: id={row_id} {version}")
            for row_id, version in stale_rows:
                await cur.execute("DELETE FROM aerich WHERE id=%s", (row_id,))
                print(f"[登记修复] 已删除无效记录: id={row_id} {version}")
            for num, name in missing_files:
                if num > resolved_fake_max:
                    continue
                await cur.execute(
                    "INSERT INTO aerich (version, app, content) VALUES (%s, %s, %s)",
                    (name, app, FAKE_CONTENT),
                )
                print(f"[登记修复] 已补记录: {name}(只补记录, 未执行SQL)")
            await conn.commit()
            return pending_real, planned_changes
    finally:
        conn.close()


async def apply_pending_migrations(app: str) -> None:
    """执行漏记文件里的SQL(真改表结构), 执行完由aerich补上记录并保存真实的模型快照。"""
    ensure_project_import()
    from aerich import Command
    from backend.configure import PROJECT_CONFIG

    command = Command(app=app, tortoise_config=build_tortoise_config(PROJECT_CONFIG, app), location=str(MIGRATION_DIR.parent))
    await command.init()
    try:
        migrated = await command.upgrade(run_in_transaction=True)
    finally:
        await command.close()
    print(f"[真实应用] SQL执行完成, 已应用文件: {migrated}")


async def apply_pending_migrations_with_hint(app: str, pending_real: list[tuple[int, str]]) -> None:
    """执行漏记文件的SQL, 失败时告诉用户怎么换一种方式重跑。"""
    pending_names = [name for _, name in pending_real]
    print(f"\n[真实应用] 开始执行 {len(pending_names)} 个漏记文件的SQL: {pending_names}")
    try:
        await apply_pending_migrations(app)
    except Exception as exc:
        print(f"\n[真实应用] 执行失败: {exc}")
        print("[提示] 如果错误是\"列已存在/表已存在\", 说明这些文件的SQL早就执行过了,")
        print("       重新选择[2]登记修复, 查漏补缺范围输入<已执行过的最大序号>再跑一遍即可。")
        raise


def preview_next_migrate(app: str) -> None:
    """预演下次迁移会执行哪些SQL并打印(只是演算, 不落盘不执行), 标出删列/改列名高风险操作。"""
    ensure_project_import()
    from aerich import Migrate
    from aerich.utils import get_models_describe

    # Migrate的操作列表是所有调用共享的, 每次演算前先清空, 防止上一次的结果混进来
    Migrate.upgrade_operators = []
    Migrate.downgrade_operators = []
    Migrate._upgrade_fk_m2m_index_operators = []
    Migrate._downgrade_fk_m2m_index_operators = []
    Migrate._upgrade_m2m = []
    Migrate._downgrade_m2m = []
    Migrate._rename_fields = {}
    new_content = get_models_describe(app)
    Migrate.diff_models(Migrate._last_version_content, new_content, no_input=True)
    Migrate.diff_models(new_content, Migrate._last_version_content, False, no_input=True)
    Migrate._merge_operators()
    operators = Migrate.upgrade_operators
    if not operators:
        print("[预览] 下次迁移不会有任何SQL: 模型和上次快照一模一样, 重启服务也不会生成新的迁移文件。")
        return
    print(f"[预览] 下次迁移将执行 {len(operators)} 条SQL:")
    drop_count = 0
    rename_count = 0
    for index, operator in enumerate(operators, start=1):
        print(f"    {index}. {operator.strip()}")
        upper_sql = operator.upper()
        if "DROP" in upper_sql:
            drop_count += 1
        elif "RENAME" in upper_sql:
            rename_count += 1
    print(f"[预览] 风险统计: 删列(DROP) {drop_count} 条, 改列名(RENAME) {rename_count} 条。")
    print("[预览] 说明: 改列名(RENAME)在真正迁移时需要人工确认, 生产上无人值守会卡住, 建议先在开发环境生成迁移文件;")
    print("[预览]       如果出现你没预期的删列(DROP), 说明快照和模型已经对不上, 务必人工确认后再执行, 否则会丢字段数据!")


async def check_baseline_and_preview(app: str, rebuild: bool, preview_enabled: bool) -> bool:
    """检查aerich表最新记录的快照是否完整(rebuild为True且快照为空时, 用当前模型重建一份); 然后预演下次迁移。返回快照是否有效。"""
    ensure_project_import()
    from aerich import Migrate
    from backend.configure import PROJECT_CONFIG
    from tortoise import connections

    # aerich的Migrate.init会先用app查快照再赋值app, 调用前必须先设置否则报错
    Migrate.app = app
    await Migrate.init(build_tortoise_config(PROJECT_CONFIG, app), app, str(MIGRATION_DIR.parent))
    try:
        last = await Migrate.get_last_version()
        if last is None:
            print("[基线] 数据库里还没有任何记录, 没有快照可用; 空数据库请走应用启动时的自动初始化。")
            return False
        baseline_ok = bool(Migrate._last_version_content)
        if baseline_ok:
            print(f"[基线] 快照完整: 最新记录 {last.version}, 里面有 {len(Migrate._last_version_content)} 个模型的信息。")
        else:
            print(f"[基线] 警告: 最新记录 {last.version} 的快照是空的, 下次迁移会误以为数据库是空的, 生成全量建表SQL!")
            if rebuild:
                from aerich.utils import get_models_describe

                last.content = get_models_describe(app)
                await last.save(update_fields=["content"])
                Migrate._last_version_content = last.content
                baseline_ok = True
                print(f"[基线] 已重建: {last.version} 的快照已换成当前模型的完整信息({len(last.content)}个模型)。")
                print("[基线] 注意: 新快照来自当前模型, 接下来预演显示\"没有SQL\"并不代表数据库结构和模型真的一致。")
            else:
                print("[基线] 怎么修: 选择菜单[3]重建基线(前提: 所有迁移文件都已经真实执行过)。")
        if not preview_enabled:
            return baseline_ok
        if baseline_ok:
            preview_next_migrate(app)
        else:
            print("[预览] 快照无效, 没法预演; 请先选择[2]修复数据库, 再选择[3]重建基线。")
        return baseline_ok
    finally:
        await connections.close_all()


async def verify_repair(app: str) -> bool:
    """复查: 数据库和文件一一对应、没有重复记录、新文件序号接得上、快照完整。"""
    files = list_migration_files()
    max_num = max(num for num, _ in files) if files else -1
    conn = await open_db_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id, version FROM aerich WHERE app=%s ORDER BY id", (app,))
            rows: list[tuple[int, str]] = await cur.fetchall()
            await cur.execute("SELECT id, version FROM aerich WHERE app=%s ORDER BY id DESC LIMIT 1", (app,))
            last = await cur.fetchone()
            await cur.execute("SELECT content FROM aerich WHERE app=%s ORDER BY id DESC LIMIT 1", (app,))
            last_content = (await cur.fetchone())[0]

        version_count: dict[str, int] = {}
        for _, version in rows:
            version_count[version] = version_count.get(version, 0) + 1
        duplicated = {version for version, count in version_count.items() if count > 1}

        ok = True
        print(f"\n[校验] 数据库记录 {len(rows)} 条; 磁盘文件 {len(files)} 个")
        if len(rows) == len(files) and not duplicated:
            print("[校验] 通过: 数据库和文件一一对应, 没有重复记录。")
        else:
            ok = False
            print(f"[校验] 失败: 记录数和文件数对不上, 或有重复记录: {sorted(duplicated)}")
        last_num = int(last[1].split("_")[0]) if last else -1
        if last is not None and last_num == max_num:
            print(f"[校验] 通过: 最新记录 {last[1]} 就是最高序号的文件, 下一个新迁移文件会用序号 {max_num + 1}, 不会重名冲突。")
        else:
            ok = False
            print(f"[校验] 失败: 最新记录的序号({last_num})和最高文件的序号({max_num})不一致, 下次生成新文件会重名冲突!")
        if last_content is None or str(last_content).strip() in ("{}", "null", ""):
            ok = False
            print("[校验] 失败: 最新记录的快照是空的, 下次迁移会生成全量建表SQL!")
        else:
            print("[校验] 通过: 最新记录的快照是完整的。")
        return ok
    finally:
        conn.close()


def read_input(prompt: str) -> str:
    """读一行用户输入; 没有输入可读时(比如被程序调用)提示后退出。"""
    try:
        return input(prompt).strip().lower()
    except EOFError:
        print("\n没有检测到输入, 已退出。")
        raise SystemExit(0) from None


def confirm(prompt: str, default: bool = False) -> bool:
    """问一句"是否继续", 直接回车等于否。"""
    default_hint = "[Y/n]" if default else "[y/N]"
    raw = read_input(f"{prompt} {default_hint}: ")
    if not raw:
        return default
    return raw in ("y", "yes")


def prompt_fake_max() -> str:
    """问查漏补缺范围, 直接回车用默认值。"""
    raw = read_input(f"查漏补缺范围(输入auto/all/数字, 直接回车用 {DEFAULT_FAKE_MAX}): ")
    if not raw:
        return DEFAULT_FAKE_MAX
    if raw in ("auto", "all") or raw.isdigit():
        return raw
    print(f"输入的\"{raw}\"不认识, 改用默认值 {DEFAULT_FAKE_MAX}。")
    return DEFAULT_FAKE_MAX


def print_menu() -> None:
    """打印功能菜单。"""
    print("-" * 90)
    print(" aerich 迁移修复工具：")
    print(" 修复数据库(aerich表)登记, 不动业务表结构; 每一步改动前都会先让你确认")
    print(f" 迁移文件目录: {MIGRATION_DIR}")
    print("-" * 90)
    print(" [1] 体检诊断   只看不动: 数据库记录和迁移文件对不对得上、快照完不完整, 顺便预演下次迁移")
    print(" [2] 登记修复   把数据库记录修到和迁移文件一致: 删掉重复和无效的记录, 补上漏记的(超范围的真实执行SQL)")
    print(" [3] 重建基线   数据库最新记录的快照为空时, 用当前模型重新生成, 防止下次迁移生成全量建表SQL")
    print(" [4] 迁移预览   只看不动: 预演下次迁移会执行哪些SQL, 重点标出删列(DROP)和改列名(RENAME)")
    print(" [5] 结果校验   只看不动: 复查数据库和文件一一对应、新文件序号接得上、快照完整")
    print(" [0] 一键修复   按顺序自动做完: 登记修复 -> 执行SQL -> 重建基线 -> 预演 -> 校验(开头确认一次)")
    print(" [q] 退出")
    print("-" * 90)


async def capability_diagnose(app: str, fake_max: str) -> None:
    """体检诊断: 全程只看不动。"""
    await repair_records(app, fake_max, execute=False, assume_yes=True)
    await check_baseline_and_preview(app, rebuild=False, preview_enabled=True)
    await verify_repair(app)


async def capability_repair_records(app: str) -> None:
    """登记修复: 先列清单, 确认后再动手。"""
    fake_max = prompt_fake_max()
    await repair_records(app, fake_max, execute=True, assume_yes=False)


async def capability_rebuild_baseline(app: str) -> None:
    """重建基线: 快照为空时用当前模型重造一份, 前提是所有迁移文件都已真实执行过。"""
    if not confirm("重建会用当前模型的完整信息, 覆盖数据库里那条空快照(只在它是空的时候才会动), 继续?"):
        print("[基线] 已取消, 没有改动。")
        return
    await check_baseline_and_preview(app, rebuild=True, preview_enabled=False)


async def capability_preview(app: str) -> None:
    """迁移预览: 打印下次迁移会执行的SQL, 统计删列/改列名数量。"""
    await check_baseline_and_preview(app, rebuild=False, preview_enabled=True)


async def capability_verify(app: str) -> None:
    """结果校验: 只读复查一遍。"""
    verify_ok = await verify_repair(app)
    print("[校验] 全部通过。" if verify_ok else "[校验] 有失败项, 请看上面的说明处理!")


async def capability_full_fix(app: str, fake_max: str) -> None:
    """一键修复: 依次执行 登记修复/执行SQL/重建基线/预演/校验。"""
    if not confirm("一键修复会按顺序执行: 修复数据库 -> 执行漏记SQL -> 重建基线 -> 预演 -> 校验, 继续?"):
        print("[一键修复] 已取消, 没有改动。")
        return
    pending_real, planned_changes = await repair_records(app, fake_max, execute=True, assume_yes=True)
    if planned_changes == 0:
        print("[一键修复] 数据库本来就是对齐的, 跳过修复这一步。")
    if pending_real:
        await apply_pending_migrations_with_hint(app, pending_real)
    baseline_ok = await check_baseline_and_preview(app, rebuild=True, preview_enabled=True)
    verify_ok = await verify_repair(app)
    print("\n[一键修复] 全部完成。" if baseline_ok and verify_ok else "\n[一键修复] 有失败项, 请看上面的说明处理!")


async def interactive_main(app: str, fake_max: str) -> None:
    """菜单循环: 打印菜单, 等输入, 一直服务到退出。"""
    while True:
        print_menu()
        choice = read_input("请选择功能编号: ")
        if choice in ("q", "quit", "exit"):
            print("已退出。")
            return
        if choice == "0":
            await capability_full_fix(app, fake_max)
        elif choice == "1":
            await capability_diagnose(app, fake_max)
        elif choice == "2":
            await capability_repair_records(app)
        elif choice == "3":
            await capability_rebuild_baseline(app)
        elif choice == "4":
            await capability_preview(app)
        elif choice == "5":
            await capability_verify(app)
        else:
            print(f"没有 \"{choice}\" 这个选项, 请输入菜单里的编号。")
        print()


if __name__ == "__main__":
    os.chdir(BACKEND_DIR)
    asyncio.run(interactive_main(DEFAULT_APP, DEFAULT_FAKE_MAX))

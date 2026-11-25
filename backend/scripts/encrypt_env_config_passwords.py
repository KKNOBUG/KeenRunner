#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/11/25 10:00:00
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : encrypt_env_config_passwords
@DateTime: 2026/11/25 10:00:00

环境配置密码存量刷库脚本：把 krun_autotest_env_config.config_password 的存量明文
统一加密为RSA密文（与前端提交口径一致：RSA-2048 + PKCS1 v1.5，base64后344字符）。

幂等：已符合密文特征（base64可解、344字符、解码256字节）的行跳过，可重跑；
含软删行（软删记录可恢复启用，同样需要密文态）。
前置：config_password 列已扩容到512（aerich迁移），脚本启动时校验列宽，不满足直接终止。
安全：默认 dry-run 仅打印计划；--apply 单事务执行，写前备份受影响行原始值到
backend/output/env_password_backup_{db}_{时间戳}.json；超245字节的明文无法单块加密，按行跳过并列入清单。

用法（仓库根目录，连接信息读 backend/.env）：
    backend/.venv/bin/python -m backend.scripts.encrypt_env_config_passwords
    backend/.venv/bin/python -m backend.scripts.encrypt_env_config_passwords --apply
"""
import argparse
import base64
import binascii
import datetime
import json
import os
import sys

import pymysql

from backend.configure import PROJECT_CONFIG
from backend.services.transport_crypto import encrypt_password

_BACKENDER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TABLE = "krun_autotest_env_config"
_CIPHER_TEXT_LENGTH = 344
_CIPHER_BYTES = 256


def _is_cipher(value: str) -> bool:
    """与保存期 assert_cipher_format 同口径的密文特征判定。"""
    if len(value) != _CIPHER_TEXT_LENGTH:
        return False
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return False
    return len(raw) == _CIPHER_BYTES


def _connect() -> pymysql.connections.Connection:
    return pymysql.connect(
        host=PROJECT_CONFIG.DATABASE_HOST,
        port=int(PROJECT_CONFIG.DATABASE_PORT),
        user=PROJECT_CONFIG.DATABASE_USERNAME,
        password=PROJECT_CONFIG.DATABASE_PASSWORD,
        database=PROJECT_CONFIG.DATABASE_NAME,
        charset="utf8mb4",
        autocommit=False,
    )


def _assert_column_width(conn) -> None:
    """列宽不足512时密文会被截断，必须先完成扩列迁移再刷库。"""
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT CHARACTER_MAXIMUM_LENGTH FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME='config_password'",
            (PROJECT_CONFIG.DATABASE_NAME, _TABLE),
        )
        row = cursor.fetchone()
    width = int(row[0]) if row else 0
    if width < 512:
        print(f"[终止] config_password 列宽={width}，需先执行扩列迁移(>=512)再刷库")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="环境配置密码存量明文刷库为RSA密文")
    parser.add_argument("--apply", action="store_true", help="实际写库（默认dry-run仅打印计划）")
    args = parser.parse_args()

    conn = _connect()
    try:
        _assert_column_width(conn)
        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT id, env_type, config_name, config_password FROM {_TABLE} "
                f"WHERE config_password IS NOT NULL AND config_password != ''"
            )
            rows = cursor.fetchall()

        skipped_cipher = 0
        skipped_oversize = []
        plan = []
        for row_id, env_type, config_name, password in rows:
            if _is_cipher(password):
                skipped_cipher += 1
                continue
            if len(password.encode("utf-8")) > 245:
                skipped_oversize.append((row_id, env_type, config_name))
                continue
            plan.append((row_id, env_type, config_name, encrypt_password(password)))

        print(f"总行数={len(rows)}, 已是密文跳过={skipped_cipher}, 待加密={len(plan)}, 超长跳过={len(skipped_oversize)}")
        for row_id, env_type, config_name in skipped_oversize:
            print(f"[超长跳过] id={row_id}, env_type={env_type}, config_name={config_name}")
        if not plan:
            print("无待加密行，结束")
            return
        if not args.apply:
            for row_id, env_type, config_name, _cipher in plan:
                print(f"[计划] id={row_id}, env_type={env_type}, config_name={config_name}")
            print("dry-run 结束；确认无误后追加 --apply 执行")
            return

        # 写前备份受影响行原始值，便于意外时人工恢复
        stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        backup_path = os.path.join(
            PROJECT_CONFIG.OUTPUT_DIR,
            f"env_password_backup_{PROJECT_CONFIG.DATABASE_NAME}_{stamp}.json",
        )
        original_map = {str(row_id): password for row_id, _t, _n, password in rows}
        backup = {str(row_id): original_map[str(row_id)] for row_id, _t, _n, _c in plan}
        os.makedirs(PROJECT_CONFIG.OUTPUT_DIR, exist_ok=True)
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(backup, f, ensure_ascii=False, indent=2)
        print(f"原始值已备份: {backup_path}")

        with conn.cursor() as cursor:
            for row_id, _env_type, _config_name, cipher in plan:
                cursor.execute(
                    f"UPDATE {_TABLE} SET config_password=%s WHERE id=%s",
                    (cipher, row_id),
                )
        conn.commit()
        print(f"刷库完成: 加密写入={len(plan)} 行")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
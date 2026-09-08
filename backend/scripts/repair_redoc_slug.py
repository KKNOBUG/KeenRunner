# -*- coding: utf-8 -*-
r"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : scripts/patch_redoc_cjk_slug
@DateTime: 2026/9/8

修复 ReDoc 文档页(/KeenRunner/redoc)左侧菜单分组无法展开、菜单项跳转异常的问题。

背景:
    ReDoc 内置的 slugify(bundle 内 webpack 模块, 实现同 slugify npm 1.x) 的默认
    白名单正则仅保留 ASCII 词字符与少量符号($*_+~.()'"!-:@等), 汉字全部被剥离。
    本项目接口 tag 统一为「中文:中文」格式(半角冒号), 剥离后所有 tag 的 slug
    全部坍缩为同一个 ":"(锚点呈 #tag/:/operation/...), 菜单目录 id 两两重复;
    点击任一分组后 hash 回流按 id 查找时永远命中第一个分组, 表现为分组点不开、
    跳转异常, 只有先点过分组内的接口项(接口 id 含唯一 operationId)才能间接展开后续分组。
    tag 命名格式有业务含义不可更改, 故对 vendor 静态文件 redoc.standalone.js 打本地补丁。

修复动作(幂等, 默认 dry-run 只打印不改动):
    在 slugify 白名单正则中加入 CJK 区段(CJK扩展A U+3400-U+4DBF 与基本区 U+4E00-U+9FFF),
    使「中文:中文」tag 的 slug 保留原文而天然唯一; 拉丁字母音译等其余行为不变。
    正则处同步留下补丁标记注释; 若日后重新下载替换 bundle 导致补丁丢失, 重跑本脚本即可恢复。

用法:
    backend/.venv/bin/python backend/scripts/patch_redoc_cjk_slug.py            # dry-run
    backend/.venv/bin/python backend/scripts/patch_redoc_cjk_slug.py --execute  # 实际写入
"""
import argparse
import sys
from pathlib import Path

BACKEND_DIR: Path = Path(__file__).resolve().parent.parent
BUNDLE_PATH: Path = BACKEND_DIR / "static" / "redoc" / "bundles" / "redoc.standalone.js"

# slugify 默认白名单正则字面量原文(bundle 内全文件唯一; 必须含前导斜杠整体替换, 避免只替换正则体时与注释拼接成 "//*" 行注释)
ORIGIN_REGEX: str = r"""/[^\w\s$*_+~.()'"!\-:@]+/g"""
# 补丁后的白名单正则字面量: 追加 CJK 扩展A(3400-4DBF) 与基本区(4E00-9FFF)
PATCHED_REGEX: str = r"""/[^\w\s$*_+~.()'"!\-:@\u3400-\u4dbf\u4e00-\u9fff]+/g"""
# 补丁标记注释, 同时作为补丁来源的可检索线索
PATCH_MARKER: str = (
    "/*KeenRunner本地补丁(scripts/patch_redoc_cjk_slug.py):"
    "slugify白名单保留CJK,避免中文tag锚点坍缩为同一值*/"
)


def patch_redoc_bundle(execute: bool) -> None:
    """对 ReDoc standalone bundle 的 slugify 白名单正则追加 CJK 区段, 幂等。"""
    if not BUNDLE_PATH.exists():
        print(f"[失败] 目标文件不存在: {BUNDLE_PATH}")
        sys.exit(1)
    content: str = BUNDLE_PATH.read_text(encoding="utf-8")
    if PATCH_MARKER in content or PATCHED_REGEX in content:
        print(f"[跳过] 已打过补丁, 无需重复处理: {BUNDLE_PATH}")
        return
    hit_count: int = content.count(ORIGIN_REGEX)
    if hit_count != 1:
        print(f"[失败] 原始白名单正则命中 {hit_count} 处(预期 1), bundle 可能已被替换或升级, 请人工核对后重试")
        sys.exit(1)

    replacement: str = f"{PATCH_MARKER} {PATCHED_REGEX}"
    if not execute:
        print("[dry-run] 命中 1 处, 将执行替换(--execute 后生效):")
        print(f"  旧: {ORIGIN_REGEX}")
        print(f"  新: {replacement}")
        return

    BUNDLE_PATH.write_text(content.replace(ORIGIN_REGEX, replacement, 1), encoding="utf-8")
    patched: str = BUNDLE_PATH.read_text(encoding="utf-8")
    if PATCHED_REGEX not in patched:
        print("[失败] 写入后校验未通过, 请检查文件")
        sys.exit(1)
    print(f"[完成] 补丁已写入: {BUNDLE_PATH}")
    print("提示: 浏览器需强制刷新(Cmd+Shift+R)以绕过本地缓存的旧 JS")


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description="ReDoc slugify CJK 本地补丁(幂等)")
    parser.add_argument("--execute", action="store_true", help="实际写入文件, 默认 dry-run")
    args: argparse.Namespace = parser.parse_args()
    patch_redoc_bundle(execute=args.execute)


if __name__ == "__main__":
    main()

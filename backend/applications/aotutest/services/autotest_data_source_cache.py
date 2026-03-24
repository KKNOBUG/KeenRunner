# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_data_source_cache.py
@DateTime: 2026/3/6
"""
import json
from typing import Optional, Dict, Any, List, Tuple

from backend import LOGGER

REDIS_KEY_PREFIX = "autotest:data_source"


def _redis_client():
    """获取 Redis 客户端（decode_responses=True）。未配置或不可用时返回 None。"""
    try:
        from backend import PROJECT_CONFIG
        import redis
        return redis.Redis.from_url(
            PROJECT_CONFIG.REDIS_URL,
            decode_responses=True,
        )
    except Exception as e:
        LOGGER.warning(f"Redis 不可用，数据源将仅从 DB 读取: {e}")
        return None


def get_by_cache_key(cache_key: str) -> Optional[Tuple[Dict[str, Any], List[str]]]:
    """
    按 cache_key 从 Redis 读取该步骤的数据。
    :return: (dataset, dataset_names) 或 None（未命中）。
    """
    client = _redis_client()
    if not client:
        return None
    try:
        raw = client.get(cache_key)
        if not raw:
            return None
        data = json.loads(raw)
        dataset = data.get("dataset") or data.get("parsed_data")
        return (dataset, data.get("dataset_names") or [])
    except Exception as e:
        LOGGER.warning(f"Redis get_by_cache_key 失败: {e}")
        return None
    finally:
        try:
            client.close()
        except Exception:
            pass


def set_parsed_data_by_cache_key(
    cache_key: str,
    dataset: Dict[str, Any],
    dataset_names: List[str],
) -> bool:
    """按 cache_key 写入/覆盖 Redis（该步骤的数据）。"""
    client = _redis_client()
    if not client:
        return False
    try:
        value = json.dumps({"dataset": dataset, "dataset_names": dataset_names}, ensure_ascii=False)
        client.set(cache_key, value)
        return True
    except Exception as e:
        LOGGER.warning(f"Redis set_parsed_data_by_cache_key 失败: {e}")
        return False
    finally:
        try:
            client.close()
        except Exception:
            pass


def delete_by_cache_key(cache_key: str) -> bool:
    """删除 Redis 中该 cache_key。"""
    client = _redis_client()
    if not client:
        return False
    try:
        client.delete(cache_key)
        return True
    except Exception as e:
        LOGGER.warning(f"Redis delete_by_cache_key 失败: {e}")
        return False
    finally:
        try:
            client.close()
        except Exception:
            pass


async def get_parsed_data_for_execution(
    data_source_code: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[List[str]]]:
    """
    执行时取数：按 data_source_code 从 DB 查询该文件下所有步骤记录，合并为完整 parsed_data。
    :return: (parsed_data, dataset_names)，parsed_data 格式 { "step_code": { "场景1": {...}, ... }, ... }；
             若不存在则 (None, None)。
    """
    from backend.applications.aotutest.services.autotest_data_source_crud import AUTOTEST_DATA_SOURCE_CRUD

    records = await AUTOTEST_DATA_SOURCE_CRUD.get_list_by_data_source_code(
        data_source_code=data_source_code,
        state=0,
    )
    if not records:
        return None, None

    parsed_data: Dict[str, Any] = {}
    dataset_names: List[str] = []
    for rec in records:
        if rec.step_code and rec.dataset is not None:
            parsed_data[rec.step_code] = rec.dataset
        if rec.dataset_names and not dataset_names:
            dataset_names = rec.dataset_names or []
    if not parsed_data:
        return None, None
    return parsed_data, dataset_names

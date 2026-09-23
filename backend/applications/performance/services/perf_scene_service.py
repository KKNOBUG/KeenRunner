# -*- coding: utf-8 -*-
"""
压测场景服务：跨实体编排(场景 + 负载预设一体化保存/批量派生/批量下发)。

职责边界：
- save_wizard：场景独立编辑页 4 Tab 一次提交的唯一入口, 内部按顺序 upsert scene → diff upsert presets;
- batch_duplicate_presets：拐点测试快捷操作, 基于已有预设批量派生多个并发档位;
- run_all_presets：一键批量下发场景下所有预设执行, 复用单预设下发链路(run_preset + apply_async)。

写操作一律走既有 Crud 入口(scene_curd/preset_curd), 不直接调用 model 层写方法,
遵循 production-project-guard 第 5 节「写操作收敛单一入口」。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_scene_service.py
@DateTime: 2026/9/22 10:00
"""
from __future__ import annotations

import traceback
from typing import Any, Dict, List, Optional

from backend.applications.performance.models.perf_load_preset_model import PerfLoadPresetModel
from backend.applications.performance.models.perf_scene_model import PerfSceneModel
from backend.applications.performance.schemas.perf_load_preset_schema import (
    PerfLoadPresetCreate,
    PerfLoadPresetLocate,
    PerfLoadPresetUpdate,
)
from backend.applications.performance.schemas.perf_scene_schema import (
    PerfPresetBatchDuplicate,
    PerfSceneCreate,
    PerfSceneLocate,
    PerfSceneUpdate,
    PerfSceneWizardPayload,
    PerfSceneWizardPresetDelete,
)
from backend.applications.performance.services.perf_load_preset_crud import PerfLoadPresetCrud
from backend.applications.performance.services.perf_scene_crud import PerfSceneCrud
from backend.configure import LOGGER
from backend.core.exceptions import ParameterException
from backend.enums import PerfPresetStatus


class PerfSceneService:
    """场景 + 负载预设跨实体编排服务(独立编辑页/拐点测试快捷操作专用)。"""

    # ---------- 一体化保存 ----------
    @staticmethod
    async def save_wizard(
            payload: PerfSceneWizardPayload,
            *,
            current_user: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        场景独立编辑页 4 Tab 一次提交入口: upsert scene + diff upsert presets。

        入参 presets 元素三种形态(按优先级判定):
        - PerfSceneWizardPresetDelete(_delete=True): 软删, 按 preset_id/preset_code 定位;
        - PerfLoadPresetUpdate(含 preset_id 或 preset_code): 更新;
        - PerfLoadPresetCreate(其余): 新增, scene_code 由本方法用保存后的场景 code 覆盖。

        执行顺序: 先保存场景 → 再处理预设(新增/更新时强制回写 scene_code 与 preset_project
        与场景实体保持一致, 防止前端漏传或漂移)。

        :param payload: PerfSceneWizardPayload(scene + presets)
        :param current_user: 当前用户账号(归因 created_user/updated_user)
        :return: {"scene": PerfSceneModel, "presets": List[PerfLoadPresetModel]}
        """
        scene_curd = PerfSceneCrud()
        preset_curd = PerfLoadPresetCrud()

        # 1. 场景 upsert: 有 scene_id/scene_code 视为更新, 否则新建
        scene_in = payload.scene
        is_scene_update = isinstance(scene_in, PerfSceneUpdate) and (scene_in.scene_id or scene_in.scene_code)
        if is_scene_update:
            if current_user:
                scene_in.updated_user = current_user
            scene: PerfSceneModel = await scene_curd.update_perf_scene(scene_in=scene_in)
        else:
            if not isinstance(scene_in, PerfSceneCreate):
                # 入参是 Update 但缺定位字段: 视为新建, 用 Update 字段构造 Create
                scene_in = PerfSceneCreate(**scene_in.model_dump(exclude={"scene_id", "scene_code", "updated_user"}))
            if current_user:
                scene_in.created_user = current_user
            scene = await scene_curd.create_perf_scene(scene_in=scene_in)

        # 2. 预设 diff upsert: 保持入参顺序处理, 失败即抛出(不做部分成功)
        saved_presets: List[PerfLoadPresetModel] = []
        for item in payload.presets or []:
            if isinstance(item, PerfSceneWizardPresetDelete) or getattr(item, "_delete", False):
                await preset_curd.delete_perf_preset(
                    preset_id=getattr(item, "preset_id", None),
                    preset_code=getattr(item, "preset_code", None),
                )
                continue
            if isinstance(item, PerfLoadPresetUpdate) and (item.preset_id or item.preset_code):
                # 更新: 强制回写场景归属与所属应用, 保证与场景实体一致
                item.scene_code = scene.scene_code
                item.scene_id = scene.id
                item.scene_name = scene.scene_name
                item.preset_project = scene.scene_project
                if current_user:
                    item.updated_user = current_user
                saved_presets.append(await preset_curd.update_perf_preset(preset_in=item))
                continue
            # 新增: Update 无定位字段时按 Create 处理; Create 直接落库
            create_data = item.model_dump(exclude={"preset_id", "preset_code", "updated_user", "_delete"})
            create_data.update({
                "scene_code": scene.scene_code,
                "scene_id": scene.id,
                "scene_name": scene.scene_name,
                "preset_project": scene.scene_project,
            })
            if current_user:
                create_data["created_user"] = current_user
            create_in = PerfLoadPresetCreate(**create_data)
            saved_presets.append(await preset_curd.create_perf_preset(preset_in=create_in))

        return {"scene": scene, "presets": saved_presets}

    # ---------- 拐点测试: 批量派生并发档位 ----------
    @staticmethod
    async def batch_duplicate_presets(
            payload: PerfPresetBatchDuplicate,
            *,
            current_user: Optional[str] = None,
    ) -> List[PerfLoadPresetModel]:
        """
        基于已有预设批量派生多个并发档位(拐点测试快捷操作)。

        以 base_preset 为模板, 仅覆盖 concurrent_users 与 preset_name; 其余字段
        (load_mode/spawn_rate/run_duration/step_*/target_rps/env_*/scene_*)全量平移。
        派生失败即抛出(不做部分成功), 由调用方决定回滚策略。

        :param payload: PerfPresetBatchDuplicate(基准预设 + 并发列表 + 可选名称模板)
        :param current_user: 当前用户账号(归因 created_user)
        :return: 新建的负载预设列表
        """
        preset_curd = PerfLoadPresetCrud()
        if payload.base_preset_id:
            base = await preset_curd.get_by_id(preset_id=payload.base_preset_id, on_error=True, state__not=1)
        else:
            base = await preset_curd.get_by_code(preset_code=payload.base_preset_code, on_error=True, state__not=1)

        created: List[PerfLoadPresetModel] = []
        for users in payload.concurrent_users_list:
            name = (payload.name_template or "{name}-{users}").format(name=base.preset_name, users=users)
            data: Dict[str, Any] = {
                "preset_project": base.preset_project,
                "preset_name": name,
                "preset_desc": base.preset_desc,
                "scene_code": base.scene_code,
                "env_name": base.env_name,
                "env_config_name": base.env_config_name,
                "load_mode": base.load_mode,
                "concurrent_users": users,
                "spawn_rate": base.spawn_rate,
                "run_duration": base.run_duration,
                "step_start_users": base.step_start_users,
                "step_increment": base.step_increment,
                "step_duration": base.step_duration,
                "step_max_users": base.step_max_users,
                "step_sustain_duration": base.step_sustain_duration,
                "target_rps": base.target_rps,
            }
            if current_user:
                data["created_user"] = current_user
            created.append(await preset_curd.create_perf_preset(preset_in=PerfLoadPresetCreate(**data)))
        return created

    # ---------- 一键跑全部预设 ----------
    @staticmethod
    async def run_all_presets(
            locate_in: PerfSceneLocate,
            *,
            current_user: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        一键批量下发场景下所有预设执行(拐点测试批量施压)。

        锁定态(queued/running/stopping)的预设跳过, 避免与既有执行冲突;
        下发失败的预设不阻塞其余预设, 逐条记录结果后统一返回。

        :param locate_in: 场景定位入参(scene_id 或 scene_code)
        :param current_user: 当前用户账号(Celery 归因)
        :return: {"scene_id": int, "scene_code": str, "total": int,
                  "dispatched": int, "skipped": int, "failed": int,
                  "items": [{"preset_id", "preset_code", "preset_name", "status", "error"}]}
        """
        from backend.applications.performance.services.perf_execute_service import PerfExecuteService
        from backend.celery_scheduler.tasks.task_performance import run_perf_preset

        scene_curd = PerfSceneCrud()
        if locate_in.scene_id:
            scene = await scene_curd.get_by_id(scene_id=locate_in.scene_id, on_error=True, state__not=1)
        else:
            scene = await scene_curd.get_by_code(scene_code=locate_in.scene_code, on_error=True, state__not=1)

        presets: List[PerfLoadPresetModel] = await PerfLoadPresetModel.filter(
            scene_code=scene.scene_code, state__not=1,
        ).order_by("id")
        if not presets:
            error_message = f"场景[scene_code={scene.scene_code}]下没有可执行的负载预设"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        locked_states = (PerfPresetStatus.QUEUED, PerfPresetStatus.RUNNING, PerfPresetStatus.STOPPING)
        items: List[Dict[str, Any]] = []
        dispatched = skipped = failed = 0
        for preset in presets:
            row: Dict[str, Any] = {
                "preset_id": preset.id,
                "preset_code": preset.preset_code,
                "preset_name": preset.preset_name,
                "status": None,
                "error": None,
            }
            if preset.last_execute_state in locked_states:
                row["status"] = "skipped"
                row["error"] = f"当前状态[{preset.last_execute_state.value}]锁定中, 跳过下发"
                skipped += 1
                items.append(row)
                continue
            try:
                instance = await PerfExecuteService.run_preset(
                    preset_in=PerfLoadPresetLocate(preset_id=preset.id),
                )
                run_perf_preset.apply_async(
                    kwargs={"preset_code": instance.preset_code, "created_user": current_user}
                )
                row["status"] = "dispatched"
                dispatched += 1
            except Exception as e:
                LOGGER.error(
                    f"一键跑全部预设下发失败: preset_code={preset.preset_code}, "
                    f"错误描述: {e}\n{traceback.format_exc()}"
                )
                row["status"] = "failed"
                row["error"] = str(getattr(e, "message", None) or e)
                failed += 1
            items.append(row)

        return {
            "scene_id": scene.id,
            "scene_code": scene.scene_code,
            "total": len(presets),
            "dispatched": dispatched,
            "skipped": skipped,
            "failed": failed,
            "items": items,
        }

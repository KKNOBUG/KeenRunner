# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_data_source2_view
@DateTime: 2026/4/10 15:35
"""
import hashlib
import json
import os.path
import shutil
import traceback
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import List
from urllib.parse import quote

import aiofiles.os as aos
from fastapi import APIRouter, File, Form
from fastapi import UploadFile
from starlette.responses import StreamingResponse

from backend.applications.aotutest.models.autotest_model import AutoTestApiStepInfo
from backend.applications.aotutest.schemas.autotest_data_generate_schema import AutoTestApiDataCreateCreate
from backend.applications.aotutest.schemas.autotest_data_source_schema import AutoTestDataSourceCreate
from backend.applications.aotutest.schemas.autotest_step_schema import AutoTestApiStepUpdate
from backend.applications.aotutest.services.autotest_data_source2_crud import AUTOTEST_API_DATA_CREATE_CRUD, AUTOTEST_API_DATA_SOURCE_CRUD
from backend.applications.aotutest.services.autotest_step_crud import AUTOTEST_API_STEP_CRUD
from backend.applications.aotutest.services.autotest_xlsx_engine import save_case_sheet, xlsx_to_json_async
from backend.configure import LOGGER
from backend.configure import PROJECT_CONFIG
from backend.core.responses import FailureResponse, SuccessResponse
from backend.services.file_transfer import FileTransfer

autotest_data_source2 = APIRouter()


async def replace_json_key(json_str, json_key_mapping):
    data = json.loads(json_str)
    new_data = {json_key_mapping.get(k, k): v for k, v in data.items()}
    new_json_str = json.dumps(new_data)
    return new_json_str


async def calc_file_hash(file: UploadFile, case_id, step_id, chunk_size: int = 8192):
    sha256 = hashlib.sha256()
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        sha256.update(chunk)
    await file.seek(0)

    return sha256.hexdigest() + f"_{case_id}_{step_id}"


@autotest_data_source2.post(path="/upload_step", summary="步骤数据源上传")
async def upload_file_step(
        case_id: int = Form(..., title="案例ID"),
        case_code: str = Form(..., title="案例CODE"),
        step_id: int = Form(..., title="步骤ID"),
        step_code: str = Form(..., title="步骤CODE"),
        step_name: str = Form(..., title="步骤名称"),
        file: UploadFile = File(..., title="案例数据源文件")
):
    if not file.filename.endswith(".xlsx"):
        return FailureResponse(message=f"仅支持xlsx格式文件")
    file_hash = await calc_file_hash(file, case_id, step_id)
    instance_hash = await AUTOTEST_API_DATA_SOURCE_CRUD.get_by_hash(file_hash=file_hash)
    instance_code = await AUTOTEST_API_DATA_SOURCE_CRUD.get_by_code(step_code=step_code)
    if not instance_hash:
        save_path = os.path.join(PROJECT_CONFIG.OUTPUT_UPLOAD_DIR, "autotest")
        if not os.path.isdir(save_path):
            os.makedirs(save_path, exist_ok=True)
        save_neo_name = os.path.join(save_path, f"{case_code}.xlsx")
        save_state, save_file_name = await FileTransfer.save_upload_file_chunks(
            upload_file=file,
            destination=save_path,
            check_filetype=False,
            check_filesize=False,
            add_left_identifier=str(uuid.uuid4())
        )
        if not save_state:
            return FailureResponse(message=f"交易失败，文件保存失败: {save_file_name}")
        await save_case_sheet(Path(save_neo_name), Path(save_file_name), step_name)
        try:
            step_info: AutoTestApiStepInfo = await AutoTestApiStepInfo.filter(
                case_id=case_id, step_code=step_code,
                state__not=1
            ).first()
            base_message = step_info.request_body
            if isinstance(base_message, dict):
                base_json = base_message
            else:
                base_json = json.loads(base_message)
            # requests_body_key = list(base_json.keys())
            requests_body_key = {"sheet1": list(base_json.keys())}
            if len(requests_body_key.get("sheet1")) != 2:
                requests_body_key = {"sheet1": []}
            result = await xlsx_to_json_async(save_file_name, requests_body_key, first_sheet_only=True)
            if result.get("valid"):
                data_source_info = AutoTestDataSourceCreate(
                    case_id=case_id,
                    step_code=step_code,
                    file_name=file.filename,
                    file_hash=file_hash,
                    file_path=save_file_name,
                    dataset=result.get("data").get("sheet1"),
                    dataset_names=list(list(result.get("data").values())[0].keys()),
                    cache_key=f"dataset_{case_id}_{step_code}",
                )
                instance_neo = await AUTOTEST_API_DATA_SOURCE_CRUD.create_data_source(data_in=data_source_info)
                await AUTOTEST_API_STEP_CRUD.update_step(
                    step_in=AutoTestApiStepUpdate(step_id=step_id, file_name=file.filename))
                data = await instance_neo.to_dict(
                    exclude_fields={
                        "state",
                        "file_path",
                        "created_user", "updated_user",
                        "created_time", "updated_time",
                        "reserve_1", "reserve_2", "reserve_3", "reserve_4", "reserve_5"
                    },
                )
                if instance_code:
                    if not instance_code.file_hash.endswith("X"):
                        # os.remove(instance_code.file_path)
                        if await aos.path.exists(instance_code.file_hash):
                            await aos.remove(instance_code.file_path)

                return SuccessResponse(message="交易成功", data=data)
            else:
                return FailureResponse(message="交易失败", data=result)
        except Exception as e:
            LOGGER.error(f"新增用例失败，异常描述: {e}\n{traceback.format_exc()}")
            return FailureResponse(message=f"交易失败，异常描述: {e}")
    return SuccessResponse(message="交易成功", data=instance_hash)


@autotest_data_source2.post(path="/upload-case", summary="案例数据源上传")
async def upload_file_steps(
        case_info: str = Form(..., title="案例信息"),
        file: UploadFile = File(..., title="案例数据源文件")
):
    if not file.filename.endswith(".xlsx"):
        return FailureResponse(message=f"仅支持xlsx格式文件")
    steps_data = json.loads(case_info)
    case_id = steps_data.get("case").get("case_id")
    case_code = steps_data.get("case").get("case_code")
    file_hash = await calc_file_hash(file, case_id, "X")
    instance_hash = await AUTOTEST_API_DATA_SOURCE_CRUD.get_by_hash(file_hash=file_hash)
    try:
        if not instance_hash:
            save_path = os.path.join(PROJECT_CONFIG.OUTPUT_UPLOAD_DIR, str(case_id))
            if not os.path.isdir(save_path):
                os.makedirs(save_path, exist_ok=True)
            save_neo_name = os.path.join(save_path, f"{case_code}.xlsx")
            save_state, save_file_name = await FileTransfer.save_upload_file_chunks(
                upload_file=file,
                destination=save_path,
                check_filetype=False,
                check_filesize=False,
                add_left_identifier=str(uuid.uuid4())
            )
            if not save_state:
                return FailureResponse(message=f"交易失败，文件保存失败: {save_file_name}")
            shutil.copyfile(save_file_name, save_neo_name)
        else:
            save_file_name = instance_hash.file_path
        steps_info: List[AutoTestApiStepInfo] = await AutoTestApiStepInfo.filter(case_id=case_id, state__not=1).all()
        requests_body_key = {}
        for step_info in steps_info:
            base_message = step_info.request_body
            if isinstance(base_message, dict):
                base_json = base_message
            else:
                base_json = json.loads(base_message)
            # requests_body_key = list(base_json.keys())
            requests_body_key[step_info.step_name] = list(base_json.keys())
            if len(requests_body_key) != 2:
                requests_body_key[step_info.step_name] = []
        result = await xlsx_to_json_async(save_file_name, requests_body_key)
        # result = await xlsx_to_json_async(save_file_name)
        if result.get("valid"):
            result_data = []
            for k, v in result.get("data").items():
                for j in steps_data.get("steps"):
                    if k == j.get("step_name"):
                        data_source_info = AutoTestDataSourceCreate(
                            case_id=case_id,
                            step_code=j.get("step_code"),
                            file_name=file.filename,
                            file_hash=file_hash,
                            file_path=save_file_name,
                            dataset=result.get("data").get(k),
                            dataset_names=list(result.get("data").get(k).keys()),
                            cache_key=f"dataset_{case_id}_{j.get('step_code')}",
                        )
                        instance_neo = await AUTOTEST_API_DATA_SOURCE_CRUD.create_data_source(
                            data_in=data_source_info)
                        await AUTOTEST_API_STEP_CRUD.update_step(
                            step_in=AutoTestApiStepUpdate(step_code=j.get("step_code"), file_name=file.filename))
                        data = await instance_neo.to_dict(
                            exclude_fields={
                                "state",
                                "file_hash",
                                "created_user", "updated_user",
                                "created_time", "updated_time",
                                "reserve_1", "reserve_2", "reserve_3", "reserve_4", "reserve_5"
                            },
                        )
                        result_data.append(data)
                        break
            return SuccessResponse(message="交易成功", data=result_data)
        else:
            return FailureResponse(message="交易失败", data=result)
    except Exception as e:
        LOGGER.error(f"新增用例失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"交易失败，异常描述: {e}")


@autotest_data_source2.post(path="/query_names", summary="案例数据场景查询")
async def query_case_name(
        case_id: str = Form(..., title="案例ID")
):
    instance_code = await AUTOTEST_API_DATA_SOURCE_CRUD.get_by_case(case_id=case_id)
    if not instance_code:
        return FailureResponse(message="ID对应场景不存在")

    return SuccessResponse(message="交易成功，任务已提交", data=instance_code.dataset_names)


@autotest_data_source2.post(path="/download_step", summary="步骤数据源下载")
async def download_file_step(
        step_code: str = Form(..., title="步骤CODE"),
        step_name: str = Form(..., title="步骤名称"),
        case_name: str = Form(..., title="脚本名称")
):
    instance_code = await AUTOTEST_API_DATA_SOURCE_CRUD.get_by_code(step_code=step_code)
    if not instance_code:
        return FailureResponse(message="步骤对应文件不存在")
    download_path = instance_code.file_path
    if not os.path.isfile(download_path):
        return FailureResponse(message="步骤对应文件不存在")
    today_str = date.today().strftime("%Y%m%d")
    file_name = quote(f"{step_name}_{case_name}_{today_str}.xlsx".encode('utf-8'))
    return StreamingResponse(
        content=FileTransfer.iter_download_file_chunks(download_file=download_path),
        media_type="application/octet-stream",
        headers={
            "fileName": file_name,
            "Content-Disposition": f"attachment; filename*=utf-8''{file_name}"
        }
    )


@autotest_data_source2.post(path="/download_case", summary="案例数据源下载")
async def download_file_step(
        case_id: int = Form(..., title="案例ID"),
        case_code: str = Form(..., title="案例CODE"),
        case_name: str = Form(..., title="脚本名称")
):
    file_path = os.path.join(PROJECT_CONFIG.OUTPUT_UPLOAD_DIR, str(case_id), f"{case_code}.xlsx")
    if not os.path.isfile(file_path):
        return FailureResponse(message="案例对应文件不存在")
    today_str = date.today().strftime("%Y%m%d")
    file_name = quote(f"{case_name}_{today_str}.xlsx".encode('utf-8'))
    return StreamingResponse(
        content=FileTransfer.iter_download_file_chunks(download_file=file_path),
        media_type="application/octet-stream",
        headers={
            "fileName": file_name,
            "Content-Disposition": f"attachment; filename*=utf-8''{file_name}"
        }
    )


@autotest_data_source2.post(path="/template", summary="测试模板下载")
async def download_file_temple(
        file_type: str = Form(..., title="模板类型")
):
    temple_type = {
        "0": "接口模板.xlsx",
        "1": "数据模板.xlsx"
    }
    if file_type not in temple_type.keys():
        return FailureResponse(message="模板对应文件不存在")
    file_path = os.path.join(PROJECT_CONFIG.OUTPUT_DOWNLOAD_DIR, temple_type.get(file_type))
    if not os.path.isfile(file_path):
        return FailureResponse(message="模板对应文件不存在")
    file_name = quote(temple_type.get(file_type).encode('utf-8'))
    return StreamingResponse(
        content=FileTransfer.iter_download_file_chunks(download_file=file_path),
        media_type="application/octet-stream",
        headers={
            "fileName": file_name,
            "Content-Disposition": f"attachment; filename*=utf-8''{file_name}"
        }
    )


@autotest_data_source2.post(path="/upload_api_doc", summary="接口文档上传")
async def upload_file_create(
        case_id: int = Form(..., title="案例ID"),
        step_id: int = Form(..., title="步骤ID"),
        step_code: str = Form(..., title="步骤CODE"),
        step_name: str = Form(..., title="步骤NAME"),
        rules_list: str = Form(..., title="生成规则"),
        file: UploadFile = File(..., title="案例数据源文件")
):
    rules_dict = {
        0: "required",
        1: "length",
        2: "enum",
        3: "decimal",
    }
    file_hash = await calc_file_hash(file, case_id, f"{rules_list}_{step_id}")
    try:
        instance_hash = await AUTOTEST_API_DATA_CREATE_CRUD.get_by_hash(file_hash=file_hash)
        if instance_hash:
            if instance_hash.create_status != 2:
                return FailureResponse(message="该文件已存在相同数据，请更换文件或修改对应测试步骤")
            else:
                return FailureResponse(message="该文件上次生成测试数据失败，请核对修改文件信息")

        step_info: AutoTestApiStepInfo = await AutoTestApiStepInfo.filter(case_id=case_id, step_code=step_code,
                                                                          state__not=1).first()
        base_message = step_info.request_body
        save_path = os.path.join(PROJECT_CONFIG.OUTPUT_UPLOAD_DIR, str(case_id))
        if not os.path.isdir(save_path):
            os.makedirs(save_path, exist_ok=True)
        save_state, save_file_name = await FileTransfer.save_upload_file_chunks(
            upload_file=file,
            destination=save_path,
            check_filetype=False,
            check_filesize=False,
            add_left_identifier=str(uuid.uuid4())
        )

        if not save_state:
            return FailureResponse(message=f"交易失败，文件保存失败: {save_file_name}")
        today_str = datetime.now().strftime("%Y%m%d%H%M%S")
        # 步骤名称 - 任务提交时间yyyymmdd
        output_excel = os.path.join(save_path, f"{step_name}-{today_str}.xlsx")
        instance_create = await AUTOTEST_API_DATA_CREATE_CRUD.create_data_create(
            data_in=AutoTestApiDataCreateCreate(
                case_id=case_id,
                step_code=step_code,
                create_status="0",
                file_name=os.path.basename(output_excel),
                file_hash=file_hash,
                file_path=save_file_name,
                dataset={}
            )
        )
        rules = [rules_dict.get(i) for i in list(map(int, rules_list.split(",")))]
        # from celery_scheduler.tasks.task_create_data import task_create_autotest_data
        # task_create_autotest_data.delay(save_file_name, output_excel, rules, base_message, instance_create.id)
        from backend.applications.aotutest.services.autotest_xlsx_create import generate_test_data
        await generate_test_data(
            input_excel=save_file_name,
            output_excel=output_excel,
            rules=rules,
            json_message=base_message,
            create_id=instance_create.id)
        return SuccessResponse(message="交易成功，任务已提交")
    except Exception as e:
        return FailureResponse(message=f"交易异常，{e}")


@autotest_data_source2.post(path="/download_api_data", summary="接口数据下载")
async def download_file_create(
        create_code: str = Form(..., title="创建CODE"),
):
    instance_hash = await AUTOTEST_API_DATA_CREATE_CRUD.get_by_code(create_code=create_code)
    if not instance_hash:
        return FailureResponse(message="不存在关联数据，请重试")

    case_id = instance_hash.case_id
    file_name = instance_hash.file_name
    file_path = os.path.join(PROJECT_CONFIG.OUTPUT_UPLOAD_DIR, str(case_id), file_name)

    if not os.path.isfile(file_path):
        return FailureResponse(message="对应文件不存在")
    file_name = quote(file_name.encode('utf-8'))
    return StreamingResponse(
        content=FileTransfer.iter_download_file_chunks(download_file=file_path),
        media_type="application/octet-stream",
        headers={
            "fileName": file_name,
            "Content-Disposition": f"attachment; filename*=utf-8''{file_name}"
        }
    )


@autotest_data_source2.post(path="/query_create", summary="接口数据记录查询")
async def query_file_create(
        step_code: str = Form(..., title="步骤CODE"),
):
    instance = await AUTOTEST_API_DATA_CREATE_CRUD.get_by_step(step_code=step_code)
    if not instance:
        return SuccessResponse(message="查询成功", data=[])
    data_list = []
    for i in instance:
        data = await i.to_dict(
            exclude_fields={
                "state",
                "file_path",
                "created_user", "updated_user",
                "reserve_1", "reserve_2", "reserve_3", "reserve_4", "reserve_5"
            },
        )
        data_list.append(data)
    return SuccessResponse(message="查询成功", data=data_list)


@autotest_data_source2.post(path="/delete_create", summary="接口数据记录删除")
async def query_file_create(
        create_code: str = Form(..., title="生成CODE"),
        step_code: str = Form(..., title="步骤CODE")):
    instance = await AUTOTEST_API_DATA_CREATE_CRUD.delete_data_create(create_code=create_code)
    if not instance:
        return FailureResponse(message="不存在关联数据，请重试")
    data = await instance.to_dict(
        exclude_fields={
            "state",
            "file_path",
            "created_user", "updated_user",
            "created_time", "updated_time",
            "reserve_1", "reserve_2", "reserve_3", "reserve_4", "reserve_5"
        },
    )
    return SuccessResponse(message="删除成功", data=data)


@autotest_data_source2.post(path="/autotest/delete-source", summary="数据源上传记录删除")
async def delete_file_create(
        step_code: str = Form(..., title="步骤CODE")):
    instance = await AUTOTEST_API_DATA_SOURCE_CRUD.get_by_code(step_code=step_code)
    if not instance:
        return FailureResponse(message="不存在关联数据，请重试")
    await AUTOTEST_API_STEP_CRUD.update_step(
        step_in=AutoTestApiStepUpdate(step_code=step_code, file_name=""))
    data = await instance.to_dict(
        exclude_fields={
            "state",
            "file_path",
            "created_user", "updated_user",
            "created_time", "updated_time",
            "reserve_1", "reserve_2", "reserve_3", "reserve_4", "reserve_5"
        },
    )
    if not instance.file_hash.endswith("X"):
        instance.file_hash = ""
        await instance.save()
        # os.remove(instance.file_path)
        await aos.remove(instance.file_path)
    return SuccessResponse(message="删除成功", data=data)

# @autotest_data_source2.post(path="/autotest/delete-source-create", summary="测试步骤删除同步数据源上传记录删除")
# async def delete_step_create(
#         case_id: str = Form(..., title="案例ID"),
#         step_code: str = Form(..., title="步骤CODE")):
#     await AUTOTEST_API_STEP_CRUD.update_step(
#         step_in=AutoTestApiStepUpdate(step_code=step_code, file_name=""))
#     instance = await AUTOTEST_API_DATA_SOURCE_CRUD.delete_data_source(step_code=step_code)
#     await AutoTestApiDataCreateInfo.filter(step_code=step_code, state__not=1).update(state=1)
#     if not instance:
#         return FailureResponse(message="不存在关联数据，请重试")
#     if not instanceinstance.file_hash.endswith("X"):
#         if await aos.path.exists(instance.file_hash):
#             await aos.remove(instance.file_hash)
#     steps_info = await AutoTestApiDataCreateInfo.filter(step_code=step_code).all()
#     for step_info in steps_info:
#         if step_info:
#             file_path = AUTO_TEST_UPLOAD_DIR / str(case_id) / step_info.file_name
#             if await aos.path.exists(file_path):
#                 await aos.remove(file_path)
#             if await aos.path.exists(step_info.file_path):
#                 await aos.remove(step_info.file_path)
#     return SuccessResponse(message="删除成功", data={})

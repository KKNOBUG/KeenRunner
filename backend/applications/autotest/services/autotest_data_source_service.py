# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_data_source_service.py
@DateTime: 2026/8/17

数据源业务服务：位于视图层与CRUD/解析器之间的无状态函数集合。

职责分组（按数据源操作链路组织）：
- 用例/步骤/数据源定位：resolve_case_and_step/resolve_enabled_data_source，及ensure_request_step/ensure_case_allows_data_source准入校验
- 矩阵落库：apply_dataframe_payload（前端矩阵解析清洗）
- 路径收集与矩阵构建：从步骤报文采集JSONPath/XPath生成垂直矩阵（/build接口）
- 字段同步：sync_data_source_fields（按报文最新字段重建矩阵，/update_fields接口；正交易场景新增字段按报文原始值回填）
- 步骤元信息回写：sync_step_data_source_meta/clear_step_data_source_meta
- 场景名称与身份补齐：场景列提取、重复检测、新建身份生成（树保存一致性校验消费）
"""
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree

import orjson

from backend.applications.autotest.dependencies import AutoTestServices
from backend.applications.autotest.models.autotest_case_model import AutoTestCaseModel
from backend.applications.autotest.models.autotest_data_source_model import AutoTestDataSourceModel
from backend.applications.autotest.models.autotest_step_model import AutoTestStepModel
from backend.applications.autotest.schemas.autotest_data_source_schema import AutoTestDataSourceCreate
from backend.applications.autotest.services.autotest_data_source_crud import make_cache_key
from backend.applications.autotest.services.autotest_data_source_parser import DataSourceMatrixParser
from backend.core.exceptions import NotFoundException, ParameterException
from backend.enums import AutoTestReqArgsType, AutoTestStepType, PUBLIC_CASE_TYPES
from backend.services import get_current_username

__all__ = ["DataSourceService"]


class DataSourceService:
    """
    数据源业务服务：位于视图层与CRUD/解析器之间的无状态函数集合。

    职责分组（按数据源操作链路组织）：
    - 用例/步骤/数据源定位：resolve_case_and_step/resolve_enabled_data_source，及ensure_request_step/ensure_case_allows_data_source准入校验
    - 矩阵落库：apply_dataframe_payload（前端矩阵解析清洗）
    - 路径收集与矩阵构建：从步骤报文采集JSONPath/XPath生成垂直矩阵（/build接口）
    - 字段同步：sync_data_source_fields（按报文最新字段重建矩阵，/update_fields接口；正交易场景新增字段按报文原始值回填）
    - 步骤元信息回写：sync_step_data_source_meta/clear_step_data_source_meta
    - 场景名称与身份补齐：场景列提取、重复检测、新建身份生成（树保存一致性校验消费）
    """

    # ==================== 常量 ====================
    DEFAULT_SCENE_NAMES: Tuple[str, ...] = ("场景1名称",)
    NORMAL_SCENE_NAME: str = "正交易场景"
    REQUEST_STEP_TYPES: Tuple = (AutoTestStepType.HTTP, AutoTestStepType.TCP)
    # 数据源指针清理覆盖的步骤类型：在REQUEST_STEP_TYPES基础上纳入引用公共接口（用户脚本宿主的引用步骤可挂数据源，删除/解绑时须同步清指针防悬空）
    CLEAR_META_STEP_TYPES: Tuple = (AutoTestStepType.HTTP, AutoTestStepType.TCP, AutoTestStepType.QUOTE_PUBLIC_API)

    # ==================== 通用工具 ====================

    @staticmethod
    def _text(value: Optional[str]) -> str:
        """去空白后的字符串。"""
        return (value or "").strip()

    @staticmethod
    def _field(item: Any, name: str, default: Any = None) -> Any:
        """兼容dict与对象属性读取。"""
        if isinstance(item, dict):
            return item.get(name, default)
        return getattr(item, name, default)

    @staticmethod
    def _enum_value(raw: Any) -> str:
        """枚举或字符串转为枚举值文本。"""
        if raw is None:
            return ""
        return str(getattr(raw, "value", raw) or "")

    # ==================== 定位与校验 ====================

    @staticmethod
    async def resolve_case_and_step(
            services: AutoTestServices,
            case_id: Optional[int] = None,
            case_code: Optional[str] = None,
            step_id: Optional[int] = None,
            step_code: Optional[str] = None,
    ) -> Tuple[AutoTestCaseModel, AutoTestStepModel]:
        """
        定位用例与步骤，并校验步骤属于该用例。

        :param services: CRUD聚合
        :param case_id: 用例主键，与case_code二选一，id优先
        :param case_code: 用例标识
        :param step_id: 步骤主键，与step_code二选一，id优先
        :param step_code: 步骤标识
        :return: (用例, 步骤)
        """
        has_case = bool(case_id) or bool(DataSourceService._text(case_code))
        has_step = bool(step_id) or bool(DataSourceService._text(step_code))
        if not (has_case and has_step):
            raise ParameterException(message="请提供(case_id或case_code)且(step_id或step_code)")
        case: AutoTestCaseModel = await services.case_curd.get_by_unique(case_id=case_id, case_code=case_code, state__not=1)
        step: AutoTestStepModel = await services.step_curd.get_by_unique(step_id=step_id, step_code=step_code, state__not=1)
        if step.case_id != case.id:
            raise NotFoundException(message=f"未命中对应用例步骤, case_id={case.id}, step_id={step.id}")
        return case, step

    @classmethod
    def ensure_request_step(cls, step: AutoTestStepModel, case: Optional[AutoTestCaseModel] = None) -> None:
        """
        仅HTTP/TCP请求步骤允许绑定数据源；用户脚本宿主下的引用公共接口步骤除外（数据源挂载在宿主引用步骤上）。

        :param step: 步骤模型实例
        :param case: 步骤所属用例模型实例；传入时放行用户脚本宿主下的引用公共接口步骤，不传保持仅HTTP/TCP的历史口径
        """
        if step.step_type in cls.REQUEST_STEP_TYPES:
            return
        if case is not None and case.case_type not in PUBLIC_CASE_TYPES and step.step_type == AutoTestStepType.QUOTE_PUBLIC_API:
            return
        raise ParameterException(message="仅支持对HTTP/TCP请求步骤使用数据源")

    @staticmethod
    def ensure_case_allows_data_source(case: AutoTestCaseModel) -> None:
        """公共脚本/公共接口不允许绑定数据源。"""
        if case.case_type in PUBLIC_CASE_TYPES:
            raise ParameterException(message="公共脚本/公共接口不允许使用数据源")

    @classmethod
    async def ensure_data_source_writable(
            cls,
            services: AutoTestServices,
            instance: AutoTestDataSourceModel,
            case_id: Optional[int] = None,
            case_code: Optional[str] = None,
    ) -> None:
        """
        数据源写操作准入：归属用例不允许公共类型、归属步骤须可挂载；入参携带用例定位时须与归属一致。

        按id/code定位的更新路径绕过了创建时的准入校验，更新/字段同步前必须调用。

        :param services: CRUD聚合
        :param instance: 已定位的启用中数据源
        :param case_id: 入参用例ID(可选)
        :param case_code: 入参用例标识(可选)
        :raises ParameterException: 归属用例为公共类型、入参定位与归属不一致、归属步骤不可挂载
        :raises NotFoundException: 归属用例不存在
        """
        owner_case = await services.case_curd.get_by_id(case_id=instance.case_id, on_error=True, state__not=1)
        cls.ensure_case_allows_data_source(owner_case)
        input_case_id = case_id if case_id else None
        input_case_code = str(case_code).strip() if case_code else ""
        if (input_case_id and input_case_id != instance.case_id) or (
                input_case_code and input_case_code != owner_case.case_code
        ):
            raise ParameterException(message="数据源归属用例与入参定位不一致, 不允许操作")
        owner_step = await services.step_curd.model.filter(
            case_id=instance.case_id, step_code=instance.step_code, state__not=1
        ).first()
        if owner_step is not None:
            cls.ensure_request_step(owner_step, case=owner_case)

    @classmethod
    async def resolve_datagram_source_step(cls, services: AutoTestServices, step: AutoTestStepModel) -> AutoTestStepModel:
        """
        解析报文来源步骤：引用公共接口步骤是壳（无自身报文），回落到被引用公共接口用例内的请求步骤。

        :param services: CRUD聚合
        :param step: 当前定位到的步骤
        :return: 用于构建矩阵/报文原始值的步骤；非引用步骤原样返回，未找到内部请求步骤时兜底原步骤
        """
        if step.step_type != AutoTestStepType.QUOTE_PUBLIC_API:
            return step
        inner = await services.step_curd.model.filter(
            case_id=step.quote_case_id or 0,
            step_type__in=list(cls.REQUEST_STEP_TYPES),
            state__not=1,
        ).order_by("step_no").first()
        return inner or step

    @staticmethod
    async def resolve_enabled_data_source(
            services: AutoTestServices,
            data_source_id: Optional[int] = None,
            data_source_code: Optional[str] = None,
            case_id: Optional[int] = None,
            case_code: Optional[str] = None,
            step_id: Optional[int] = None,
            step_code: Optional[str] = None,
            *,
            on_error: bool = True,
    ) -> Optional[AutoTestDataSourceModel]:
        """
        定位启用中的数据源：id/code优先，否则按用例+步骤。

        :param services: CRUD聚合
        :param data_source_id: 数据源主键
        :param data_source_code: 数据源标识
        :param case_id: 用例主键
        :param case_code: 用例标识
        :param step_id: 步骤主键
        :param step_code: 步骤标识
        :param on_error: 未找到时是否抛出异常
        :return: 数据源实例或None
        """
        if data_source_id:
            return await services.data_source_curd.get_by_id(
                data_source_id=data_source_id,
                on_error=on_error,
                state__not=1,
            )
        if DataSourceService._text(data_source_code):
            return await services.data_source_curd.get_by_code(
                data_source_code=DataSourceService._text(data_source_code),
                on_error=on_error,
                state__not=1,
            )
        case, step = await DataSourceService.resolve_case_and_step(
            services,
            case_id=case_id,
            case_code=case_code,
            step_id=step_id,
            step_code=step_code,
        )
        return await services.data_source_curd.get_by_case_step(
            case_id=case.id,
            step_code=step.step_code,
            on_error=on_error,
            state__not=1,
        )

    # ==================== 矩阵载荷 ====================

    @staticmethod
    async def apply_dataframe_payload(dataframe: Optional[List[Any]], axis: Optional[int]) -> Optional[Dict[str, Any]]:
        """
        解析并清洗二维矩阵，生成dataset/dataset_names/dataframe/axis。

        清洗后若没有任何带字段值的场景（水平空行 / 垂直空列全部被剔除），拒绝落库。

        :param dataframe: 二维矩阵
        :param axis: 调用方声明的方向；与矩阵结构冲突时以分区标记识别结果为准
        :return: 解析结果字典；dataframe为None时返回None（表示本次不改矩阵）
        """
        if dataframe is None:
            return None
        parsed_axis = axis if axis in (DataSourceMatrixParser.AXIS_HORIZONTAL, DataSourceMatrixParser.AXIS_VERTICAL) else None
        step_data, dataset_names, norm_matrix, used_axis = await DataSourceMatrixParser.parse_dataframe_matrix_async(
            dataframe,
            axis=parsed_axis,
        )
        if not step_data or not dataset_names:
            raise ParameterException(message="数据源场景数据为空，不允许保存。请至少填写一个场景的字段值")
        return {
            "dataset": step_data,
            "dataset_names": dataset_names,
            "dataframe": norm_matrix,
            "axis": used_axis,
        }

    # ==================== 路径收集与矩阵构建 ====================

    @staticmethod
    def _kv_originals(kv_list: Optional[List[Any]], *, skip_file: bool = False) -> Dict[str, Any]:
        """
        将[{key,value,type}]转为JSONPath→原始值映射，保留出现顺序并按路径去重。

        :param kv_list: 键值列表
        :param skip_file: 为True时跳过type=file的项
        :return: 形如$.key的路径到原始值的映射
        """
        originals: Dict[str, Any] = {}
        for item in kv_list or []:
            item_type = str(DataSourceService._field(item, "type") or "").strip().lower()
            if skip_file and item_type == "file":
                continue
            key = str(DataSourceService._field(item, "key") or "").strip()
            if not key:
                continue
            originals[f"$.{key}"] = DataSourceService._field(item, "value")
        return originals

    @staticmethod
    def _kv_jsonpaths(kv_list: Optional[List[Any]], *, skip_file: bool = False) -> List[str]:
        """
        将[{key,value,type}]转为JSONPath列表，保留出现顺序并去重。

        :param kv_list: 键值列表
        :param skip_file: 为True时跳过type=file的项
        :return: 形如$.key的路径列表
        """
        return list(DataSourceService._kv_originals(kv_list, skip_file=skip_file))

    @staticmethod
    def _flatten_json_leaf_values(data: Any, prefix: str = "$") -> Dict[str, Any]:
        """
        将JSON展平为叶子JSONPath→原始值映射，保留文档序，值维持原类型。

        :param data: dict/list/标量
        :param prefix: 当前路径前缀
        :return: 叶子路径到原始值的映射
        """
        originals: Dict[str, Any] = {}
        if isinstance(data, dict):
            for key, value in data.items():
                path = f"{prefix}.{key}"
                if isinstance(value, (dict, list)) and value:
                    originals.update(DataSourceService._flatten_json_leaf_values(value, path))
                else:
                    originals[path] = value
            return originals
        if isinstance(data, list):
            for index, value in enumerate(data):
                path = f"{prefix}[{index}]"
                if isinstance(value, (dict, list)) and value:
                    originals.update(DataSourceService._flatten_json_leaf_values(value, path))
                else:
                    originals[path] = value
            return originals
        return originals

    @staticmethod
    def _flatten_json_leaf_paths(data: Any, prefix: str = "$") -> List[str]:
        """
        将JSON展平为叶子JSONPath，保留文档序。

        :param data: dict/list/标量
        :param prefix: 当前路径前缀
        :return: 叶子路径列表
        """
        return list(DataSourceService._flatten_json_leaf_values(data, prefix))

    @staticmethod
    def _xml_local_name(tag: str) -> str:
        """去掉Clark命名空间，仅保留本地标签名。"""
        if tag and "}" in tag:
            return tag.rsplit("}", 1)[-1]
        return tag or ""

    @staticmethod
    def _flatten_xml_xpath_values(xml_text: str) -> Dict[str, Any]:
        """
        按文档序将XML叶子与属性展平为ElementTree XPath→文本值映射（./Child、./Child/@attr）。

        叶子值取节点文本去除首尾空白，属性值保持原样。

        :param xml_text: XML字符串
        :return: XPath到文本值的映射；非法XML返回空字典
        """
        text = str(xml_text or "").strip()
        if not text:
            return {}
        try:
            root = ElementTree.fromstring(text)
        except ElementTree.ParseError:
            return {}

        originals: Dict[str, Any] = {}

        def walk(elem: ElementTree.Element, xpath_prefix: str) -> None:
            for attr_name, attr_value in elem.attrib.items():
                local_attr = DataSourceService._xml_local_name(attr_name)
                if xpath_prefix == ".":
                    originals[f"./@{local_attr}"] = attr_value
                else:
                    originals[f"{xpath_prefix}/@{local_attr}"] = attr_value
            children = list(elem)
            if not children:
                originals["." if xpath_prefix == "." else xpath_prefix] = (elem.text or "").strip()
                return
            name_total = Counter(DataSourceService._xml_local_name(child.tag) for child in children)
            name_seen: Counter = Counter()
            for child in children:
                local = DataSourceService._xml_local_name(child.tag)
                name_seen[local] += 1
                if xpath_prefix == ".":
                    child_prefix = f"./{local}"
                else:
                    child_prefix = f"{xpath_prefix}/{local}"
                if name_total[local] > 1:
                    child_prefix = f"{child_prefix}[{name_seen[local]}]"
                walk(child, child_prefix)

        walk(root, ".")
        return originals

    @staticmethod
    def _flatten_xml_xpath_paths(xml_text: str) -> List[str]:
        """
        按文档序将XML叶子与属性展平为ElementTree XPath（./Child、./Child/@attr）。

        :param xml_text: XML字符串
        :return: XPath列表；非法XML返回空列表
        """
        return list(DataSourceService._flatten_xml_xpath_values(xml_text))

    @staticmethod
    def _parse_json_body(request_body: Any) -> Any:
        """将步骤request_body转为可展平的dict/list；无法解析则返回None。"""
        if isinstance(request_body, (dict, list)):
            return request_body
        if isinstance(request_body, str) and request_body.strip():
            try:
                loaded = orjson.loads(request_body)
            except (TypeError, orjson.JSONDecodeError):
                return None
            if isinstance(loaded, (dict, list)):
                return loaded
        return None

    @staticmethod
    def _looks_like_xml_payload(value: Any) -> bool:
        """
        判断报文文本是否以XML起始标记开头。

        :param value: 候选报文
        :return: 疑似XML返回True
        """
        if not isinstance(value, str):
            return False
        return value.lstrip("\ufeff \t\r\n").startswith("<")

    @classmethod
    def _xml_payload_text(cls, step: AutoTestStepModel) -> str:
        """
        提取步骤的XML报文本：优先request_text，缺失时兼容字符串型request_body。

        :param step: 步骤实例
        :return: XML文本；非XML或为空时返回空串
        """
        request_text = getattr(step, "request_text", None)
        if cls._looks_like_xml_payload(request_text):
            return request_text.lstrip("\ufeff \t\r\n")
        request_body = getattr(step, "request_body", None)
        if cls._looks_like_xml_payload(request_body):
            return request_body.lstrip("\ufeff \t\r\n")
        return ""

    @classmethod
    def _collect_step_partition(cls, step: AutoTestStepModel) -> Dict[str, Dict[str, Any]]:
        """
        统一采集步骤报文的HEAD与BODY分区路径及原始值。

        HEAD取自请求头键值对；BODY按request_args_type分支采集：
        JSON展平叶子、XML展平XPath、PARAMS/FORM_DATA/X_WWW_FORM_URLENCODED取键值；
        RAW/NONE/未指定类型默认无结构化字段，但正文为XML时同样按XPath展平
        （TCP/HTTP的RAW报文常直接存放XML，若只认xml类型会导致数据源矩阵与data_original为空）。

        :param step: 步骤实例(取request_args_type与报文)
        :return: 分区名→{路径→原始值}映射，如{"HEAD": {"$.Token": "x"}, "BODY": {"$.id": 1}}
        """
        result: Dict[str, Dict[str, Any]] = {
            "HEAD": dict(cls._kv_originals(getattr(step, "request_header", None))),
            "BODY": {},
        }
        args = cls._enum_value(getattr(step, "request_args_type", None)).lower()
        if args == AutoTestReqArgsType.JSON.value:
            payload = cls._parse_json_body(getattr(step, "request_body", None))
            if payload is not None:
                result["BODY"] = cls._flatten_json_leaf_values(payload)
        elif args == AutoTestReqArgsType.XML.value:
            result["BODY"] = cls._flatten_xml_xpath_values(cls._xml_payload_text(step))
        elif args in (AutoTestReqArgsType.RAW.value, AutoTestReqArgsType.NONE.value, ""):
            # RAW/NONE 不是“无报文”，只是未声明结构；正文是XML时按XML采集字段，
            # 否则保持空BODY（纯文本/十六进制报文无法生成字段路径）。
            xml_text = cls._xml_payload_text(step)
            if xml_text:
                result["BODY"] = cls._flatten_xml_xpath_values(xml_text)
        elif args == AutoTestReqArgsType.PARAMS.value:
            result["BODY"] = cls._kv_originals(getattr(step, "request_params", None))
        elif args == AutoTestReqArgsType.FORM_DATA.value:
            result["BODY"] = cls._kv_originals(getattr(step, "request_form_data", None), skip_file=True)
        elif args == AutoTestReqArgsType.X_WWW_FORM_URLENCODED.value:
            result["BODY"] = cls._kv_originals(getattr(step, "request_form_urlencoded", None))
        return result

    @classmethod
    def _collect_head_paths(cls, step: AutoTestStepModel) -> List[str]:
        """请求头键转为$.HeaderName。"""
        return list(cls._collect_step_partition(step).get("HEAD", {}))

    @classmethod
    def _collect_body_paths(cls, step: AutoTestStepModel) -> List[str]:
        """
        按请求参数类型收集BODY分区路径。

        raw/none 正文为XML时进入BODY；纯文本/十六进制及文件型form-data不进入。
        """
        return list(cls._collect_step_partition(step).get("BODY", {}))

    @classmethod
    def build_blank_vertical_matrix(cls) -> List[List[Any]]:
        """
        构建含分区标记的空白垂直矩阵模板。

        每个分区标记后跟随一行空白填充区；用例无已存数据源时使用。
        """
        empty: List[str] = [""] * len(cls.DEFAULT_SCENE_NAMES)
        matrix: List[List[Any]] = [["", *cls.DEFAULT_SCENE_NAMES]]
        for marker in ("HEAD", "BODY", "ASSERT_HEAD", "ASSERT_BODY"):
            matrix.append([marker, *empty])
            matrix.append(list(empty))
        return matrix

    @classmethod
    def build_vertical_matrix_from_step(cls, step: AutoTestStepModel) -> List[List[Any]]:
        """
        按垂直模式根据当前步骤报文构建空白场景矩阵。

        默认三列场景名；路径写入HEAD/BODY分区下，单元格值留空；
        ASSERT_HEAD/ASSERT_BODY仅保留分区标记行。
        """
        empty = [""] * len(cls.DEFAULT_SCENE_NAMES)
        matrix: List[List[Any]] = [["", *cls.DEFAULT_SCENE_NAMES]]
        matrix.append(["HEAD", *empty])
        for path in cls._collect_head_paths(step):
            matrix.append([path, *empty])
        matrix.append(["BODY", *empty])
        for path in cls._collect_body_paths(step):
            matrix.append([path, *empty])
        matrix.append(["ASSERT_HEAD", *empty])
        matrix.append(["ASSERT_BODY", *empty])
        return matrix

    @classmethod
    def collect_step_report_original(cls, step: AutoTestStepModel) -> Dict[str, Dict[str, str]]:
        """
        采集步骤报文原始值映射，按HEAD/BODY分区隔离，值统一文本化为字符串。

        路径规则与字段同步一致：请求头$.Key、JSON叶子JSONPath、XML叶子XPath、键值型$.Key；
        HEAD与BODY分区独立存放，同路径互不覆盖；逐值经dataset_cell_placeholder文本化，
        与数据源dataset字符串化存储协议对齐（类型语义由执行注入侧按报文原字段适配）。

        :param step: 步骤实例(取request_args_type与报文)
        :return: 分区名->字段路径->原始文本值映射，如{"HEAD": {"$.Token": "x"}, "BODY": {"$.id": "1"}}
        """
        originals = cls._collect_step_partition(step)
        return {
            section: {path: DataSourceMatrixParser.dataset_cell_placeholder(value) for path, value in mapping.items()}
            for section, mapping in originals.items()
        }

    # ==================== 字段同步 ====================

    @staticmethod
    def _rebuild_scene_values(
            old_values: Optional[List[Any]],
            empty: List[Any],
            normal_index: int,
            originals: Optional[Dict[str, Dict[str, Any]]],
            section: str,
            path: str,
    ) -> List[Any]:
        """
        字段同步取场景值：保留字段搬移原值；新增字段其余场景补空，正交易场景按报文原始值回填。

        :param old_values: 原矩阵中该字段的场景值行/列，字段不存在时为None
        :param empty: 补空基准(与场景数等长)
        :param normal_index: 正交易场景在场景维度中的序号，-1表示未导入
        :param originals: 报文原始值映射，按HEAD/BODY分区隔离同名字段
        :param section: 当前字段所属分区(HEAD/BODY)
        :param path: 字段路径
        :return: 该字段同步后的场景值
        """
        if old_values is not None:
            return list(old_values)
        values = list(empty)
        if normal_index >= 0 and originals:
            value = originals.get(section, {}).get(path)
            values[normal_index] = "" if value is None else value
        return values

    @classmethod
    def _rebuild_vertical_matrix(
            cls,
            matrix: List[List[Any]],
            head_paths: List[str],
            body_paths: List[str],
            originals: Optional[Dict[str, Any]] = None,
    ) -> List[List[Any]]:
        """
        垂直模式字段同步：以报文最新路径为准重建HEAD/BODY分区行，ASSERT分区原样保留。

        保留字段的场景值从原矩阵按路径匹配搬移；删除字段整行剔除；
        新增字段其余场景补空，正交易场景列按报文原始值回填(未导入正交易场景则补空)。

        :param matrix: 原垂直矩阵
        :param head_paths: 报文最新HEAD路径
        :param body_paths: 报文最新BODY路径
        :param originals: 报文原始值映射(按HEAD/BODY分区)，供正交易场景列回填新增字段值
        :return: 重建后的垂直矩阵
        """
        scene_names = DataSourceMatrixParser.extract_scene_names_from_matrix(matrix, DataSourceMatrixParser.AXIS_VERTICAL)
        col_count = 1 + len(scene_names)
        empty = [""] * len(scene_names)
        # 正交易场景在场景维度中的列号(0起)，-1表示未导入
        normal_col = scene_names.index(cls.NORMAL_SCENE_NAME) if originals and cls.NORMAL_SCENE_NAME in scene_names else -1
        # 原矩阵按分区+路径索引场景值，供保留字段搬移
        old_values: Dict[Tuple[str, str], List[Any]] = {}
        section: Optional[str] = None
        assert_rows: List[List[Any]] = []
        header_row = list(matrix[0][:col_count]) if matrix else [""]
        for row in matrix[1:]:
            if not row:
                continue
            cell = "" if row[0] is None else str(row[0]).strip()
            if DataSourceMatrixParser.is_section_marker(cell):
                section = cell.upper()
                if section in ("ASSERT_HEAD", "ASSERT_BODY"):
                    assert_rows.append(list(row[:col_count]))
                continue
            if section in ("HEAD", "BODY") and cell:
                old_values[(section, cell)] = list(row[1:col_count])
            elif section in ("ASSERT_HEAD", "ASSERT_BODY"):
                assert_rows.append(list(row[:col_count]))
        result: List[List[Any]] = [header_row]
        result.append(["HEAD", *empty])
        for path in head_paths:
            result.append([path, *cls._rebuild_scene_values(old_values.get(("HEAD", path)), empty, normal_col, originals, "HEAD", path)])
        result.append(["BODY", *empty])
        for path in body_paths:
            result.append([path, *cls._rebuild_scene_values(old_values.get(("BODY", path)), empty, normal_col, originals, "BODY", path)])
        result.extend(assert_rows)
        return result

    @classmethod
    def _rebuild_horizontal_matrix(
            cls,
            matrix: List[List[Any]],
            head_paths: List[str],
            body_paths: List[str],
            originals: Optional[Dict[str, Any]] = None,
    ) -> List[List[Any]]:
        """
        水平模式字段同步：以报文最新路径为准重建HEAD/BODY分区列，ASSERT分区原样保留。

        保留字段的场景值从原矩阵按路径匹配搬移；删除字段整列剔除；
        新增字段其余场景补空，正交易场景行按报文原始值回填(未导入正交易场景则补空)。

        :param matrix: 原水平矩阵
        :param head_paths: 报文最新HEAD路径
        :param body_paths: 报文最新BODY路径
        :param originals: 报文原始值映射(按HEAD/BODY分区)，供正交易场景行回填新增字段值
        :return: 重建后的水平矩阵
        """
        scene_names = DataSourceMatrixParser.extract_scene_names_from_matrix(matrix, DataSourceMatrixParser.AXIS_HORIZONTAL)
        # 原矩阵按分区+路径索引列，供保留字段搬移
        old_cols: Dict[Tuple[str, str], int] = {}
        section: Optional[str] = None
        assert_col_indices: List[int] = []
        header = list(matrix[0]) if matrix else []
        for col_idx in range(1, len(header)):
            cell = "" if header[col_idx] is None else str(header[col_idx]).strip()
            if DataSourceMatrixParser.is_section_marker(cell):
                section = cell.upper()
                if section in ("ASSERT_HEAD", "ASSERT_BODY"):
                    assert_col_indices.append(col_idx)
                continue
            if section in ("HEAD", "BODY") and cell:
                old_cols[(section, cell)] = col_idx
            elif section in ("ASSERT_HEAD", "ASSERT_BODY"):
                assert_col_indices.append(col_idx)
        # 正交易场景行号(原矩阵1+行序，result同序)：新增字段按报文原始值回填该行，-1表示未导入
        normal_row = -1
        if originals:
            for row_idx, row in enumerate(matrix[1:]):
                if row and str(row[0] if row[0] is not None else "").strip() == cls.NORMAL_SCENE_NAME:
                    normal_row = row_idx
                    break
        # 新列顺序：场景名列 + HEAD标记+字段列 + BODY标记+字段列 + ASSERT列原样
        # 列映射项：int=原矩阵列号；None=分区标记列；(分区, 路径)=新增字段列
        new_header: List[Any] = [header[0] if header else ""]
        new_col_map: List[Any] = [0]
        new_header.append("HEAD")
        new_col_map.append(None)
        for path in head_paths:
            new_header.append(path)
            new_col_map.append(old_cols.get(("HEAD", path)) if ("HEAD", path) in old_cols else ("HEAD", path))
        new_header.append("BODY")
        new_col_map.append(None)
        for path in body_paths:
            new_header.append(path)
            new_col_map.append(old_cols.get(("BODY", path)) if ("BODY", path) in old_cols else ("BODY", path))
        for col_idx in assert_col_indices:
            new_header.append(header[col_idx])
            new_col_map.append(col_idx)
        result: List[List[Any]] = [new_header]
        for row_idx, row in enumerate(matrix[1:]):
            new_row: List[Any] = []
            for src in new_col_map:
                if src is None:
                    new_row.append("")
                elif isinstance(src, int):
                    new_row.append(row[src] if src < len(row) else "")
                elif row_idx == normal_row:
                    value = originals.get(src[0], {}).get(src[1])
                    new_row.append("" if value is None else value)
                else:
                    new_row.append("")
            result.append(new_row)
        return result

    @classmethod
    async def sync_data_source_fields(cls, step: AutoTestStepModel, dataframe: List[Any], axis: Optional[int]) -> Dict[str, Any]:
        """
        按步骤当前报文同步数据源矩阵字段：新增字段补空值，删除字段剔除，保留字段场景值不动。

        仅同步HEAD/BODY分区，ASSERT分区原样保留，方向以矩阵实际结构为准；
        正交易场景列/行的新增字段按报文原始值回填，其余场景补空。

        :param step: 步骤实例(取request_args_type与报文)
        :param dataframe: 数据源当前二维矩阵
        :param axis: 数据源声明方向(仅作回落)
        :return: {dataset, dataset_names, dataframe, axis}更新载荷
        """
        used_axis = DataSourceMatrixParser.resolve_matrix_axis(dataframe, declared_axis=axis)
        head_paths = cls._collect_head_paths(step)
        body_paths = cls._collect_body_paths(step)
        originals = cls.collect_step_report_original(step)
        if used_axis == DataSourceMatrixParser.AXIS_VERTICAL:
            new_matrix = cls._rebuild_vertical_matrix(dataframe, head_paths, body_paths, originals)
        else:
            new_matrix = cls._rebuild_horizontal_matrix(dataframe, head_paths, body_paths, originals)
        step_data, dataset_names, norm_matrix, final_axis = await DataSourceMatrixParser.parse_dataframe_matrix_async(
            new_matrix, axis=used_axis
        )
        return {
            "dataset": step_data,
            "dataset_names": dataset_names,
            "dataframe": norm_matrix,
            "axis": final_axis,
        }

    # ==================== 场景名称 ====================

    @staticmethod
    def _scene_names_from_dataframe(dataframe: Any, axis: Any = None) -> Optional[List[str]]:
        """从 dataframe 矩阵头/首列提取场景名（单元格全空时仍可得到列名）。"""
        if not isinstance(dataframe, list) or not dataframe:
            return None
        used_axis = axis if axis in (DataSourceMatrixParser.AXIS_HORIZONTAL,
                                     DataSourceMatrixParser.AXIS_VERTICAL) else DataSourceMatrixParser.AXIS_VERTICAL
        names = DataSourceMatrixParser.extract_scene_names_from_matrix(dataframe, used_axis)
        return names or None

    @staticmethod
    def data_source_scene_names(ds: Any) -> Optional[List[str]]:
        """
        取出数据源场景列顺序：优先 dataset 的插入序，否则 dataset_names，
        再否则从 dataframe 矩阵头提取（空单元格模板也能参与一致性校验）。

        仅去掉空白名称，不去重、不排序；没有任何有效名称则返回 None。
        """
        raw: Optional[List[Any]] = None
        if isinstance(getattr(ds, "dataset", None), dict) and ds.dataset:
            raw = list(ds.dataset.keys())
        elif isinstance(getattr(ds, "dataset_names", None), list) and ds.dataset_names:
            raw = list(ds.dataset_names)
        if raw is not None:
            names: List[str] = []
            for item in raw:
                name = str(item).strip() if item is not None else ""
                if name:
                    names.append(name)
            if names:
                return names
        return DataSourceService._scene_names_from_dataframe(
            getattr(ds, "dataframe", None),
            getattr(ds, "axis", None),
        )

    @staticmethod
    def data_source_duplicate_scene_names(ds: Any) -> List[str]:
        """
        提取单个数据源内重复的场景列名称。

        优先从dataframe矩阵提取（保留重复出现），缺失时回落dataset_names；
        dataset的dict键天然去重，不可用于重复检测。

        :param ds: 数据源记录
        :return: 按首次出现顺序返回重复名称，无重复返回空列表
        """
        names = DataSourceService._scene_names_from_dataframe(getattr(ds, "dataframe", None), getattr(ds, "axis", None))
        if names is None:
            raw = getattr(ds, "dataset_names", None)
            if isinstance(raw, list):
                names = [str(item).strip() for item in raw if item is not None and str(item).strip()]
        if not names:
            return []
        counter = Counter(names)
        seen: set = set()
        duplicates: List[str] = []
        for name in names:
            if counter[name] > 1 and name not in seen:
                seen.add(name)
                duplicates.append(name)
        return duplicates

    # ==================== 步骤元信息回写 ====================

    @staticmethod
    async def sync_step_data_source_meta(
            services: AutoTestServices,
            *,
            case_id: int,
            step_code: str,
            data_source_id: Optional[int],
            file_name: Optional[str],
            file_desc: Optional[str],
    ) -> None:
        """回写步骤上的数据源指针。"""
        step_vals: Dict[str, Any] = {
            "data_source_id": data_source_id,
            "data_source_name": (file_name or "")[:2048] or None,
            "data_source_desc": (file_desc or "")[:2048] or None,
        }
        services.step_curd.fill_updated_user(step_vals)
        await services.step_curd.model.filter(
            case_id=case_id,
            step_code=step_code,
            state=0,
        ).update(**step_vals)

    @classmethod
    async def clear_step_data_source_meta(
            cls,
            services: AutoTestServices,
            *,
            case_id: int,
            step_code: Optional[str] = None,
    ) -> int:
        """清空步骤上的数据源指针；step_code为空时清空该用例全部可挂数据源步骤(含引用公共接口)。"""
        step_vals: Dict[str, Any] = {
            "data_source_id": None,
            "data_source_name": None,
            "data_source_desc": None,
        }
        services.step_curd.fill_updated_user(step_vals)
        filters: Dict[str, Any] = {
            "case_id": case_id,
            "state": 0,
            "step_type__in": list(cls.CLEAR_META_STEP_TYPES),
        }
        if cls._text(step_code):
            filters["step_code"] = cls._text(step_code)
        return await services.step_curd.model.filter(**filters).update(**step_vals)

    # ==================== 身份补齐 ====================

    @staticmethod
    def fill_create_identity(data_in: AutoTestDataSourceCreate, case: AutoTestCaseModel, step: AutoTestStepModel) -> AutoTestDataSourceCreate:
        """用已解析的用例/步骤补齐创建入参中的标识字段。"""
        return data_in.model_copy(
            update={
                "case_id": case.id,
                "case_code": case.case_code,
                "step_id": step.id,
                "step_code": step.step_code,
                "cache_key": make_cache_key(case.id, step.step_code),
                "created_user": data_in.created_user or get_current_username(),
            }
        )

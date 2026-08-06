# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : router_crud.py
@DateTime: 2025/1/31 17:36
"""
from typing import Optional, List

from fastapi import FastAPI
from fastapi.routing import APIRoute
from tortoise.exceptions import DoesNotExist

from backend.applications.base.models.router_model import Router
from backend.applications.base.schemas.router_schema import RouterCreate, RouterUpdate
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import DataAlreadyExistsException, NotFoundException, ParameterException

class RouterCrud(ScaffoldCrud[Router, RouterCreate, RouterUpdate]):

    def __init__(self):
        super().__init__(model=Router)

    async def get_by_id(self, router_id: int, on_error: bool = True, **kwargs) -> Optional[Router]:
        """
        根据主键ID查询路由。

        :param router_id: 路由ID
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 路由实例或None
        :raises ParameterException: router_id为空
        :raises NotFoundException: on_error为True且路由不存在
        """
        if not router_id:
            error_message: str = "查询路由信息失败, 参数[router_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.get_or_none(id=router_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询路由信息失败, 记录[id={router_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_path(self, path: str, on_error: bool = True, **kwargs) -> Optional[List[Router]]:
        """
        根据路径查询路由列表(同一path可能对应多种method)。

        :param path: 路由路径
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 路由实例列表；无匹配且on_error为False时为空列表
        :raises ParameterException: path为空
        :raises NotFoundException: on_error为True且无匹配路由
        """
        if not path:
            error_message: str = "查询路由信息失败, 参数[path]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.model.filter(path=path, **kwargs).all()
        if not instance and on_error:
            error_message: str = f"查询路由信息失败, 记录[path={path}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_method(self, method: str, on_error: bool = True, **kwargs) -> Optional[List[Router]]:
        """
        根据HTTP方法查询路由列表。

        :param method: HTTP方法(如GET、POST)
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 路由实例列表；无匹配且on_error为False时为空列表
        :raises ParameterException: method为空
        :raises NotFoundException: on_error为True且无匹配路由
        """
        if not method:
            error_message: str = "查询路由信息失败, 参数[method]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.model.filter(method=method, **kwargs).all()
        if not instance and on_error:
            error_message: str = f"查询路由信息失败, 记录[method={method}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_summary(self, summary: str, on_error: bool = True, **kwargs) -> Optional[List[Router]]:
        """
        根据接口摘要查询路由列表。

        :param summary: 接口摘要
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 路由实例列表；无匹配且on_error为False时为空列表
        :raises ParameterException: summary为空
        :raises NotFoundException: on_error为True且无匹配路由
        """
        if not summary:
            error_message: str = "查询路由信息失败, 参数[summary]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.model.filter(summary=summary, **kwargs).all()
        if not instance and on_error:
            error_message: str = f"查询路由信息失败, 记录[summary={summary}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_tags(self, tags: str, on_error: bool = True, **kwargs) -> Optional[List[Router]]:
        """
        根据标签字符串查询路由列表。

        :param tags: 标签(库内逗号拼接存储)
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 路由实例列表；无匹配且on_error为False时为空列表
        :raises ParameterException: tags为空
        :raises NotFoundException: on_error为True且无匹配路由
        """
        if not tags:
            error_message: str = "查询路由信息失败, 参数[tags]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.model.filter(tags=tags, **kwargs).all()
        if not instance and on_error:
            error_message: str = f"查询路由信息失败, 记录[tags={tags}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def create_router(self, router_in: RouterCreate) -> Router:
        """
        创建路由：校验path+method唯一性后落库。

        :param router_in: 新增路由入参
        :return: 新建的路由实例
        :raises DataAlreadyExistsException: 相同path与method已存在
        """
        path = router_in.path
        method = router_in.method
        instances = await self.get_by_conditions(only_one=False, on_error=False, path=path, method=method)
        if instances:
            error_message: str = f"新增路由信息失败, 记录[path={path}, method={method}]信息已存在"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        instance = await self.create(router_in)
        return instance

    async def delete_router(self, router_id: int, **kwargs) -> Router:
        """
        根据ID物理删除单个路由。

        :param router_id: 路由ID
        :param kwargs: 额外查询条件
        :return: 被删除的路由实例
        :raises NotFoundException: 路由不存在
        """
        instance = await self.get_by_id(router_id, on_error=True, **kwargs)
        await instance.delete()
        return instance

    async def update_router(self, router_in: RouterUpdate) -> Router:
        """
        根据路由ID更新路由字段。

        :param router_in: 更新入参
        :return: 更新后的路由实例
        :raises NotFoundException: 路由不存在
        """
        router_id: int = router_in.id
        router_if: dict = router_in.model_dump(exclude_none=True)
        try:
            instance = await self.update(id=router_id, obj_in=router_if)
        except DoesNotExist as e:
            error_message: str = f"更新路由信息失败, 记录[id={router_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)

        return instance

    async def refresh_router(self, app: FastAPI) -> List[Router]:
        """
        根据FastAPI应用当前路由同步数据库：删除废弃项，新增或更新现有项。

        :param app: FastAPI应用实例
        :return: 同步后的全部路由列表
        """
        # 获取全部路由数据
        all_router_list = []
        for route in app.routes:
            # 只更新有鉴权的路由
            if isinstance(route, APIRoute) and route.methods not in ("OPTIONS",) and route.path_format not in ('/',):
                all_router_list.append((list(route.methods)[0], route.path_format))

        # 删除废弃路由数据
        for router in await self.model.all():
            if (router.method, router.path) not in all_router_list:
                await self.model.filter(method=router.method, path=router.path).delete()

        # 更新路由数据
        for route in app.routes:
            if isinstance(route, APIRoute) and route.methods not in ("OPTIONS",) and route.path_format not in ('/',):
                data = {
                    'path': route.path_format,
                    'method': list(route.methods)[0],
                    'summary': route.summary,
                    'tags': ','.join(list(route.tags)),
                    'description': route.description
                }
                instance = await self.model.filter(method=data["method"], path=data["path"]).first()
                if instance:
                    await instance.update_from_dict(data).save()
                else:
                    await self.model.create(**data)

        return await self.model.all()

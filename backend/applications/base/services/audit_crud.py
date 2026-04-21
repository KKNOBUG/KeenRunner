# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : audit_crud
@DateTime: 2026/4/20 16:53
"""
from typing import List, Optional

from backend.applications.base.models.audit_model import Audit


class AuditCrud:
    @staticmethod
    async def delete_by_ids(audit_ids: Optional[List[int]]) -> int:
        """按主键列表批量物理删除，一条 SQL（filter + delete）。"""
        if not audit_ids:
            return 0
        ids = [int(x) for x in audit_ids]
        return int(await Audit.filter(id__in=ids).delete())


AUDIT_CRUD = AuditCrud()

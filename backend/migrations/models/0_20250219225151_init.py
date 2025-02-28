from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `krun_user` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `created_user` VARCHAR(16)   COMMENT '创建人',
    `updated_user` VARCHAR(16)   COMMENT '更新人',
    `username` VARCHAR(32) NOT NULL UNIQUE COMMENT '用户账号',
    `password` VARCHAR(255)   COMMENT '用户密码',
    `alias` VARCHAR(64) NOT NULL  COMMENT '用户姓名',
    `email` VARCHAR(64) NOT NULL UNIQUE COMMENT '用户邮箱',
    `phone` VARCHAR(20) NOT NULL  COMMENT '用户电话',
    `avatar` VARCHAR(255)   COMMENT '用户头像',
    `state` SMALLINT NOT NULL  COMMENT '用户状态(0:离职,1:正常,2:休假,3:出差,4:待岗)' DEFAULT 2,
    `is_active` BOOL NOT NULL  COMMENT '是否激活' DEFAULT 1,
    `is_superuser` BOOL NOT NULL  COMMENT '是否为超级管理员' DEFAULT 0,
    `last_login` DATETIME(6)   COMMENT '最后一次登陆时间',
    `dept_id` INT   COMMENT '所属部门ID',
    KEY `idx_krun_user_usernam_f8c07b` (`username`),
    KEY `idx_krun_user_alias_bd5c3a` (`alias`),
    KEY `idx_krun_user_state_80291a` (`state`),
    KEY `idx_krun_user_is_acti_e29ecb` (`is_active`),
    KEY `idx_krun_user_is_supe_31d692` (`is_superuser`),
    KEY `idx_krun_user_last_lo_a0ca1d` (`last_login`),
    KEY `idx_krun_user_dept_id_7cb5fe` (`dept_id`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `krun_dept` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `created_user` VARCHAR(16)   COMMENT '创建人',
    `updated_user` VARCHAR(16)   COMMENT '更新人',
    `code` VARCHAR(16) NOT NULL UNIQUE COMMENT '部门代码',
    `name` VARCHAR(64) NOT NULL UNIQUE COMMENT '部门名称',
    `description` LONGTEXT   COMMENT '部门描述',
    `is_deleted` BOOL NOT NULL  COMMENT '软删除标记' DEFAULT 0,
    `order` INT NOT NULL  COMMENT '排序' DEFAULT 0,
    `parent_id` INT NOT NULL  COMMENT '父部门ID' DEFAULT 0,
    KEY `idx_krun_dept_is_dele_958cb0` (`is_deleted`),
    KEY `idx_krun_dept_order_56cdf5` (`order`),
    KEY `idx_krun_dept_parent__4977d3` (`parent_id`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `krun_dept_nest` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `ancestor` INT NOT NULL  COMMENT '父部门',
    `descendant` INT NOT NULL  COMMENT '子部门',
    `level` INT NOT NULL  COMMENT '深度' DEFAULT 0,
    KEY `idx_krun_dept_n_ancesto_222164` (`ancestor`),
    KEY `idx_krun_dept_n_descend_a21497` (`descendant`),
    KEY `idx_krun_dept_n_level_79e83a` (`level`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `krun_audit` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `user_id` BIGINT NOT NULL  COMMENT '用户ID',
    `username` VARCHAR(32) NOT NULL  COMMENT '用户名称' DEFAULT '',
    `module` VARCHAR(64) NOT NULL  COMMENT '功能模块' DEFAULT '',
    `summary` VARCHAR(128) NOT NULL  COMMENT '请求描述' DEFAULT '',
    `method` VARCHAR(16) NOT NULL  COMMENT '请求方法' DEFAULT '',
    `path` VARCHAR(255) NOT NULL  COMMENT '请求路径' DEFAULT '',
    `status` SMALLINT NOT NULL  COMMENT '状态码' DEFAULT -1,
    `response_time` INT NOT NULL  COMMENT '响应时间(单位ms)' DEFAULT 0,
    KEY `idx_krun_audit_user_id_e9d5e0` (`user_id`),
    KEY `idx_krun_audit_usernam_846619` (`username`),
    KEY `idx_krun_audit_module_cfa424` (`module`),
    KEY `idx_krun_audit_summary_149320` (`summary`),
    KEY `idx_krun_audit_method_4a293c` (`method`),
    KEY `idx_krun_audit_path_ce5cf3` (`path`),
    KEY `idx_krun_audit_status_0915be` (`status`),
    KEY `idx_krun_audit_respons_6a54ed` (`response_time`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `krun_role` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `code` VARCHAR(16) NOT NULL UNIQUE COMMENT '角色代码',
    `name` VARCHAR(64) NOT NULL UNIQUE COMMENT '角色名称',
    `description` LONGTEXT   COMMENT '角色描述'
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `krun_menu` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `name` VARCHAR(32) NOT NULL  COMMENT '菜单名称',
    `remark` JSON   COMMENT '保留字段',
    `menu_type` VARCHAR(7)   COMMENT '菜单类型',
    `icon` VARCHAR(128)   COMMENT '菜单图标',
    `path` VARCHAR(128) NOT NULL  COMMENT '菜单路径',
    `order` INT NOT NULL  COMMENT '排序' DEFAULT 0,
    `parent_id` INT NOT NULL  COMMENT '父菜单ID' DEFAULT 0,
    `is_hidden` BOOL NOT NULL  COMMENT '是否隐藏' DEFAULT 0,
    `component` VARCHAR(128) NOT NULL  COMMENT '组件',
    `keepalive` BOOL NOT NULL  COMMENT '存活' DEFAULT 1,
    `redirect` VARCHAR(128)   COMMENT '重定向',
    KEY `idx_krun_menu_name_725587` (`name`),
    KEY `idx_krun_menu_menu_ty_9060b1` (`menu_type`),
    KEY `idx_krun_menu_path_000d2c` (`path`),
    KEY `idx_krun_menu_order_03622d` (`order`),
    KEY `idx_krun_menu_parent__cfbd95` (`parent_id`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `krun_api` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `created_user` VARCHAR(16)   COMMENT '创建人',
    `updated_user` VARCHAR(16)   COMMENT '更新人',
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `path` VARCHAR(255) NOT NULL  COMMENT 'API路径',
    `method` VARCHAR(7) NOT NULL  COMMENT 'API方式',
    `summary` VARCHAR(128) NOT NULL  COMMENT 'API简介',
    `tags` VARCHAR(128) NOT NULL  COMMENT 'API标签',
    `description` LONGTEXT   COMMENT 'API描述',
    UNIQUE KEY `uid_krun_api_method_d1e166` (`method`, `path`),
    KEY `idx_krun_api_path_02e8a4` (`path`),
    KEY `idx_krun_api_summary_ca7ddf` (`summary`),
    KEY `idx_krun_api_tags_000a0c` (`tags`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `aerich` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `version` VARCHAR(255) NOT NULL,
    `app` VARCHAR(100) NOT NULL,
    `content` JSON NOT NULL
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `krun_user_role` (
    `krun_user_id` BIGINT NOT NULL,
    `role_id` BIGINT NOT NULL,
    FOREIGN KEY (`krun_user_id`) REFERENCES `krun_user` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`role_id`) REFERENCES `krun_role` (`id`) ON DELETE CASCADE,
    UNIQUE KEY `uidx_krun_user_r_krun_us_0072e7` (`krun_user_id`, `role_id`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `krun_role_menus` (
    `krun_role_id` BIGINT NOT NULL,
    `menu_id` BIGINT NOT NULL,
    FOREIGN KEY (`krun_role_id`) REFERENCES `krun_role` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`menu_id`) REFERENCES `krun_menu` (`id`) ON DELETE CASCADE,
    UNIQUE KEY `uidx_krun_role_m_krun_ro_35c485` (`krun_role_id`, `menu_id`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `krun_role_apis` (
    `krun_role_id` BIGINT NOT NULL,
    `api_id` BIGINT NOT NULL,
    FOREIGN KEY (`krun_role_id`) REFERENCES `krun_role` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`api_id`) REFERENCES `krun_api` (`id`) ON DELETE CASCADE,
    UNIQUE KEY `uidx_krun_role_a_krun_ro_47d579` (`krun_role_id`, `api_id`)
) CHARACTER SET utf8mb4;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """

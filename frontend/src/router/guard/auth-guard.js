import {getToken, isNullOrWhitespace} from '@/utils'


// 白名单，包含无需验证 token 的路径
const WHITE_LIST = ['/login', '/404'];

export function createAuthGuard(router) {
    router.beforeEach(async (to) => {
        const token = getToken()

        /** 没有 token 的情况 */
        if (isNullOrWhitespace(token)) {
            // 如果当前路径在白名单中，直接放行
            if (WHITE_LIST.includes(to.path)) {
                return true;
            }
            // 重定向到登录页，并记录原路径
            return {path: 'login', query: {...to.query, redirect: to.path}};
        }

        /** 有 token 的情况 */
        if (to.path === '/login') {
            // 有 token 时访问登录页，重定向到首页
            return {path: '/'};
        }

        // 其他情况正常放行
        return true;
    })
}



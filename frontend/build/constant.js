export const OUTPUT_DIR = 'dist'
export const BACKEND_URL = 'http://172.20.10.2:8518'
// export const BACKEND_URL = 'http://192.168.1.14:8518'
export const PROXY_CONFIG = {
    /**
     * @desc    替换匹配值
     * @请求路径  http://localhost:3100/api/user
     * @转发路径  http://localhost:9999/api/v1 +/user
     */
    '/api': {
        target: BACKEND_URL, changeOrigin: true, rewrite: (path) => path.replace(new RegExp('^/api'), ''),
    }, /**
     * @desc    不替换匹配值
     * @请求路径  http://localhost:3100/api/v1/user
     * @转发路径  http://localhost:9999/api/v1/user
     */
    // '/api/v1': {
    //   target: 'http://192.168.94.229:8518',
    //   changeOrigin: true,
    // },
}


/**
 * 开发环境额外代理：Swagger/ReDoc 页面会请求 /krun/* 与 /static/swagger-ui/*
 * 若 iframe 使用相对路径（同域）时需配合 vite server.proxy
 */
export const EXTRA_DEV_PROXY = {
    '/krun': {
        target: BACKEND_URL, changeOrigin: true,
    }, '/static': {
        target: BACKEND_URL, changeOrigin: true,
    },
}

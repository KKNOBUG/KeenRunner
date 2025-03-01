export const OUTPUT_DIR = 'dist'

export const PROXY_CONFIG = {
  /**
   * @desc    替换匹配值
   * @请求路径  http://localhost:3100/api/user
   * @转发路径  http://localhost:9999/api/v1 +/user
   */
  '/api': {
    // target: 'http://localhost:8518/',
    // target: 'http://192.168.94.229:8518',
    target: 'http://192.168.94.230:8518',
    // target: 'http://172.20.10.2:8518',
    changeOrigin: true,
    rewrite: (path) => path.replace(new RegExp('^/api'), ''),
  },
  /**
   * @desc    不替换匹配值
   * @请求路径  http://localhost:3100/api/v1/user
   * @转发路径  http://localhost:9999/api/v1/user
   */
  // '/api/v1': {
  //   target: 'http://localhost:8518/',
  //   target: 'http://192.168.94.229:8518',
  //   changeOrigin: true,
  // },
}

import {defineConfig, loadEnv} from 'vite'
import fs from 'fs'
import path from 'path'

import {convertEnv, getRootPath, getSrcPath} from './build/utils'
import {viteDefine} from './build/config'
import {createVitePlugins} from './build/plugin'
import {OUTPUT_DIR, PROXY_CONFIG, EXTRA_DEV_PROXY} from './build/constant'
import monacoEditorPlugin from 'vite-plugin-monaco-editor';

const copyDirRecursive = (src, dest) => {
  if (!fs.existsSync(dest)) fs.mkdirSync(dest, { recursive: true })
  const entries = fs.readdirSync(src, { withFileTypes: true })
  for (const entry of entries) {
    const srcPath = path.join(src, entry.name)
    const destPath = path.join(dest, entry.name)
    if (entry.isDirectory()) {
      copyDirRecursive(srcPath, destPath)
    } else {
      fs.copyFileSync(srcPath, destPath)
    }
  }
}

const copyLuckysheetDistPlugin = () => ({
  name: 'copy-luckysheet-dist',
  apply: 'build',
  writeBundle() {
    const dest = path.resolve(__dirname, OUTPUT_DIR || 'dist', 'luckysheet')
    try {
      copyDirRecursive(path.resolve(__dirname, 'node_modules/luckysheet/dist'), dest)
      fs.copyFileSync(
        path.resolve(__dirname, 'node_modules/jquery/dist/jquery.min.js'),
        path.resolve(dest, 'jquery.min.js')
      )
      console.log(`[copy-luckysheet-dist] copied to ${dest}`)
    } catch (e) {
      console.error('[copy-luckysheet-dist] copy failed:', e)
    }
  },
})

export default defineConfig(({command, mode}) => {
    const srcPath = getSrcPath()
    const rootPath = getRootPath()
    const isBuild = command === 'build'

    const env = loadEnv(mode, process.cwd())
    const viteEnv = convertEnv(env)
    const {VITE_PORT, VITE_PUBLIC_PATH, VITE_USE_PROXY, VITE_BASE_API} = viteEnv

    return {
        base: VITE_PUBLIC_PATH || '/',
        resolve: {
            alias: {
                '~': rootPath,
                '@': srcPath,
                'monaco-editor': rootPath + '/node_modules/monaco-editor/esm/vs/editor/editor.main.js'
            },
        },
        define: viteDefine,
        plugins:[
            createVitePlugins(viteEnv, isBuild),
            monacoEditorPlugin({
                languageWorkers: ['editorWorkerService', 'json', 'typescript'],
            }),
            isBuild ? copyLuckysheetDistPlugin() : null,
        ].filter(Boolean),
        server: {
            host: '0.0.0.0',
            port: VITE_PORT,
            open: true,
            proxy: VITE_USE_PROXY
                ? {
                    [VITE_BASE_API]: PROXY_CONFIG[VITE_BASE_API],
                    ...EXTRA_DEV_PROXY,
                }
                : undefined,
            // 明确配置静态资源目录
            fs: {
                allow: ['.'], // 允许访问根目录及其子目录
            },
        },
        build: {
            target: 'es2020',
            outDir: OUTPUT_DIR || 'dist',
            reportCompressedSize: false, // 启用/禁用 gzip 压缩大小报告
            chunkSizeWarningLimit: 1024, // chunk 大小警告的限制（单位kb）
        },
        // 添加 worker 配置
        worker: {
            format: 'es',
            rollupOptions: {
                external: ['monaco-editor'],
                output: {
                    // 确保 Web Worker 文件输出到正确的目录
                    entryFileNames: 'assets/[name].[hash].js',
                    chunkFileNames: 'assets/[name].[hash].js',
                    assetFileNames: 'assets/[name].[hash].[ext]',
                },
            },
        },
    }
})

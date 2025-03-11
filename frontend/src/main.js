/** 重置样式 */
import '@/styles/reset.css'
import 'uno.css'
import '@/styles/global.scss'

import {createApp} from 'vue'
import {setupRouter} from '@/router'
import {setupStore} from '@/store'
import App from './App.vue'
import MonacoEditor from "@/components/monaco/index.vue"

import {setupDirectives} from './directives'
import {useResize} from '@/utils'
import i18n from '~/i18n'

export function monaco(app) {
    app.component('monaco-editor', MonacoEditor);
}

async function setupApp() {
    const app = createApp(App)

    setupStore(app)

    await setupRouter(app)
    setupDirectives(app)
    monaco(app);
    app.use(useResize)
    app.use(i18n)
    app.mount('#app')
}

setupApp()

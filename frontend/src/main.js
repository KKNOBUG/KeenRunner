/** 重置样式 */
import '@/styles/reset.css'
import 'uno.css'
import '@/styles/global.scss'

import { createApp } from 'vue'
import { setupRouter } from '@/router'
import { setupStore } from '@/store'
import App from './App.vue'
import MonacoEditor from "@/components/monaco/index.vue"

import { setupDirectives } from './directives'
import { useResize } from '@/utils'
import i18n from '~/i18n'

//
// self.MonacoEnvironment = {
//   getWorkerUrl: function (moduleId, label) {
//     if (label === 'json') {
//       return '/assets/json.worker.js';
//       // return ~'/node_modules/monaco-editor/esm/vs/language/json/json.worker.js';
//     }
//     if (label === 'css' || label === 'scss' || label === 'less') {
//       return '/assets/css.worker.js';
//       // return ~'/node_modules/monaco-editor/esm/vs/language/css/css.worker.js';
//     }
//     if (label === 'html' || label === 'handlebars' || label === 'razor') {
//       return '/assets/html.worker.js';
//       // return ~'/node_modules/monaco-editor/esm/vs/language/html/html.worker.js';
//
//     }
//     if (label === 'typescript' || label === 'javascript') {
//       return '/assets/ts.worker.js';
//       // return ~'/node_modules/monaco-editor/esm/vs/language/typescript/ts.worker.js';
//
//     }
//     return '/assets/editor.worker.js';
//     // return ~'/node_modules/monaco-editor/esm/vs/editor/editor.worker.js';
//
//   },
// };

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

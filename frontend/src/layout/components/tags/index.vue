<template>
  <ScrollX ref="scrollXRef" class="bg-white dark:bg-dark!">
    <!-- 工作台页签不展示右侧 X 关闭按钮（closable=false），其余页签在多于 1 个时可关闭 -->
    <n-tag
        v-for="tag in tagsStore.tags"
        ref="tabRefs"
        :key="tag.path"
        class="mx-5 cursor-pointer rounded-4 px-15 hover:color-primary"
        :type="tagsStore.activeTag === tag.path ? 'primary' : 'default'"
        :closable="isTagClosable(tag)"
        @click="handleTagClick(tag.path)"
        @close.stop="tagsStore.removeTag(tag.path)"
        @contextmenu.prevent="handleContextMenu($event, tag)"
    >
      {{ tag.title }}
    </n-tag>
    <ContextMenu
        v-if="contextMenuOption.show"
        v-model:show="contextMenuOption.show"
        :current-path="contextMenuOption.currentPath"
        :x="contextMenuOption.x"
        :y="contextMenuOption.y"
    />
  </ScrollX>
</template>

<script setup>
import ContextMenu from './ContextMenu.vue'
import { useTagsStore } from '@/store'
import { WORKBENCH_TAG_PATH } from '@/store/modules/tags/helpers'
import ScrollX from '@/components/common/ScrollX.vue'

const workbenchTagPath = WORKBENCH_TAG_PATH
const route = useRoute()
const router = useRouter()
const tagsStore = useTagsStore()

/** 工作台页签不展示关闭按钮，其余页签在多于 1 个时可关闭 */
function isTagClosable(tag) {
  if (tag.path === workbenchTagPath) return false
  return tagsStore.tags.length > 1
}
const tabRefs = ref([])
const scrollXRef = ref(null)

const contextMenuOption = reactive({
  show: false,
  x: 0,
  y: 0,
  currentPath: '',
})

watch(
    () => route.path,
    () => {
      const { name, fullPath: path } = route
      const title = route.meta?.title
      tagsStore.addTag({ name, path, title })
    },
    { immediate: true },
)

watch(
    () => tagsStore.activeIndex,
    async (activeIndex) => {
      await nextTick()
      const activeTabElement = tabRefs.value[activeIndex]?.$el
      if (!activeTabElement) return
      const { offsetLeft: x, offsetWidth: width } = activeTabElement
      scrollXRef.value?.handleScroll(x + width, width)
    },
    { immediate: true },
)

const handleTagClick = (path) => {
  tagsStore.setActiveTag(path)
  router.push(path)
}

function showContextMenu() {
  contextMenuOption.show = true
}
function hideContextMenu() {
  contextMenuOption.show = false
}
function setContextMenu(x, y, currentPath) {
  Object.assign(contextMenuOption, { x, y, currentPath })
}

// 右击菜单
async function handleContextMenu(e, tagItem) {
  const { clientX, clientY } = e
  hideContextMenu()
  setContextMenu(clientX, clientY, tagItem.path)
  await nextTick()
  showContextMenu()
}
</script>

<style>
.n-tag__close {
  box-sizing: content-box;
  border-radius: 50%;
  font-size: 12px;
  padding: 2px;
  transform: scale(0.9);
  transform: translateX(5px);
  transition: all 0.3s;
}
</style>

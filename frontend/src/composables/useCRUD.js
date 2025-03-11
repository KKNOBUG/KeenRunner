import { isNullOrWhitespace } from '@/utils'

// ACTIONS 是一个对象，用于将操作类型（view、edit、add）映射为对应的中文描述。
const ACTIONS = {
  view: '查看',
  edit: '编辑',
  add: '新增',
}

/**
 * 默认导出的组合式函数
 * @param name 操作的数据名称，用于生成模态框的标题。
 * @param initForm 初始化表单数据，默认为空对象。
 * @param doCreate 新增数据的 API 调用函数。
 * @param doDelete 删除数据的 API 调用函数。
 * @param doUpdate 更新数据的 API 调用函数。
 * @param refresh 刷新数据的函数，通常用于更新列表数据。
 * @returns
 */
export default function ({ name, initForm = {}, doCreate, doDelete, doUpdate, refresh }) {
  /**
   * modalVisible：用于控制模态框的显示与隐藏，初始值为 false。
   * modalAction：表示当前模态框的操作类型（view、edit、add），初始值为空字符串。
   * modalTitle：计算属性，根据 modalAction 和 name 生成模态框的标题。
   * modalLoading：表示模态框的加载状态，初始值为 false。
   * modalFormRef：用于引用模态框中的表单组件，初始值为 null。
   * modalForm：存储模态框中的表单数据，初始值为 initForm 的副本。
   */
  const modalVisible = ref(false)
  const modalAction = ref('')
  const modalTitle = computed(() => ACTIONS[modalAction.value] + name)
  const modalLoading = ref(false)
  const modalFormRef = ref(null)
  const modalForm = ref({ ...initForm })

  /** 新增 */
  function handleAdd() {
    modalAction.value = 'add'
    modalVisible.value = true
    modalForm.value = { ...initForm }
  }

  /** 修改 */
  function handleEdit(row) {
    modalAction.value = 'edit'
    modalVisible.value = true
    modalForm.value = { ...row }
  }

  /** 查看 */
  function handleView(row) {
    modalAction.value = 'view'
    modalVisible.value = true
    modalForm.value = { ...row }
  }

  /** 保存 */
  function handleSave(...callbacks) {
    // 检查当前操作是否为 edit 或 add，如果不是则隐藏模态框并返回
    if (!['edit', 'add'].includes(modalAction.value)) {
      modalVisible.value = false
      return
    }
    // 对表单进行验证，如果验证通过，则根据 modalAction 执行相应的 API 调用，执行回调函数，显示成功消息，隐藏模态框，并刷新数据
    // 如果出现错误，则将加载状态设置为 false。
    modalFormRef.value?.validate(async (err) => {
      if (err) return
      const actions = {
        add: {
          api: () => doCreate(modalForm.value),
          cb: () => {
            callbacks.forEach((callback) => callback && callback())
          },
          msg: () => $message.success('新增成功'),
        },
        edit: {
          api: () => doUpdate(modalForm.value),
          cb: () => {
            callbacks.forEach((callback) => callback && callback())
          },
          msg: () => $message.success('编辑成功'),
        },
      }
      const action = actions[modalAction.value]

      try {
        modalLoading.value = true
        const data = await action.api()
        action.cb()
        action.msg()
        modalLoading.value = modalVisible.value = false
        data && refresh(data)
      } catch (error) {
        modalLoading.value = false
      }
    })
  }

  /** 删除 */
  async function handleDelete(params = {}) {
    // 检查传入的参数是否为空，如果为空则返回。
    if (isNullOrWhitespace(params)) return
    // 执行删除 API 调用，显示成功消息，隐藏模态框，并刷新数据。如果出现错误，则将加载状态设置为 false。
    try {
      modalLoading.value = true
      const data = await doDelete(params)
      $message.success('删除成功')
      modalLoading.value = false
      refresh(data)
    } catch (error) {
      modalLoading.value = false
    }
  }

  return {
    modalVisible,
    modalAction,
    modalTitle,
    modalLoading,
    handleAdd,
    handleDelete,
    handleEdit,
    handleView,
    handleSave,
    modalForm,
    modalFormRef,
  }
}

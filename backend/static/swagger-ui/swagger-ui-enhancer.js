(function () {
  "use strict";

  /* 常量定义: 工具栏标识 / 按钮配置 / 跳转步长 */
  var TOOLBAR_ID = "krun-docs-toolbar";
  // 工具栏收纳态类名: 收起后仅保留把手按钮, 避免窄视口下遮挡内容区点击
  var TOOLBAR_COLLAPSED_CLASS = "collapsed";
  // 上跳/下跳的固定像素步长; 超出页首/页尾可滚动范围时由浏览器自动截断, 天然形成边界无操作
  var JUMP_DISTANCE = 600;

  var TOOLBAR_BUTTONS = [
    { key: "expand", label: "展开分类", title: "一键展开所有分类(显示全部接口列表)" },
    { key: "collapse", label: "折叠分类", title: "一键折叠所有分类(含已展开的接口详情)" },
    { key: "prev", label: "向上滚动", title: "向上滚动 " + JUMP_DISTANCE + " 像素" },
    { key: "next", label: "向下滚动", title: "向下滚动 " + JUMP_DISTANCE + " 像素" },
    { key: "top", label: "跳到顶部", title: "跳转到页面顶部" },
    { key: "bottom", label: "跳到底部", title: "跳转到页面底部" },
  ];

  /* 工具函数区 */

  // 依次触发原生点击; 注意需先取快照再统一点击, React 批量更新下 DOM 类名在本次任务内不刷新,
  // 快照保证每个目标恰好被点击一次, 不会因类名未变化而重复切换
  function clickAll(nodes) {
    Array.prototype.forEach.call(nodes, function (node) {
      node.click();
    });
  }

  /* 功能区: 展开 / 折叠 */

  // 展开所有分类: 只展开分区(接口列表可见), 各接口详情保持原有展开状态
  function expandAllSections() {
    clickAll(document.querySelectorAll(".opblock-tag-section:not(.is-open) > h3.opblock-tag"));
  }

  // 折叠所有分类: 先收起已展开的接口详情, 再收起分区; 该顺序保证点击时所有目标仍挂载在 DOM 中
  function collapseAllSections() {
    clickAll(document.querySelectorAll(".opblock.is-open .opblock-summary-control"));
    clickAll(document.querySelectorAll(".opblock-tag-section.is-open > h3.opblock-tag"));
  }

  /* 功能区: 滚动与跳转 */

  // 统一使用瞬时跳转而非平滑滚动: 平滑滚动异步进行期间连续点击时, 基于中途位置的
  // 计算会失真; 瞬时跳转保证每次点击时位置已确定, 连续点击可靠推进
  function scrollToPosition(top) {
    window.scrollTo({ top: top });
  }

  // 上跳/下跳按固定像素步长滚动(不按分类定位): 目标位置越界时浏览器自动截断到
  // 页首/页尾最大可滚动距离, 无需额外边界分支
  function jumpToPrev() {
    scrollToPosition(window.scrollY - JUMP_DISTANCE);
  }

  function jumpToNext() {
    scrollToPosition(window.scrollY + JUMP_DISTANCE);
  }

  function jumpToTop() {
    scrollToPosition(0);
  }

  function jumpToBottom() {
    scrollToPosition(document.documentElement.scrollHeight);
  }

  /* 工具栏注入区 */

  var ACTION_HANDLERS = {
    expand: expandAllSections,
    collapse: collapseAllSections,
    prev: jumpToPrev,
    next: jumpToNext,
    top: jumpToTop,
    bottom: jumpToBottom,
  };

  function handleAction(event) {
    var handler = ACTION_HANDLERS[event.currentTarget.dataset.action];
    if (handler) {
      handler();
    }
  }

  function handleCollapseToggle(event) {
    var toolbar = event.currentTarget.parentNode;
    var collapsed = toolbar.classList.toggle(TOOLBAR_COLLAPSED_CLASS);
    event.currentTarget.textContent = collapsed ? "︎◀︎" : "▶︎";
  }

  function buildToolbar() {
    var toolbar = document.createElement("div");
    toolbar.id = TOOLBAR_ID;
    // 把手按钮: 窄视口下工具栏会压住内容区右缘, 提供收起开关
    var toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "krun-docs-btn krun-docs-toggle";
    toggle.textContent = "▶︎";
    toggle.title = "收起/展开工具栏";
    toggle.addEventListener("click", handleCollapseToggle);
    toolbar.appendChild(toggle);
    TOOLBAR_BUTTONS.forEach(function (config) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "krun-docs-btn";
      button.textContent = config.label;
      button.title = config.title;
      button.dataset.action = config.key;
      button.addEventListener("click", handleAction);
      toolbar.appendChild(button);
    });
    return toolbar;
  }

  function buildToolbarStyle() {
    var style = document.createElement("style");
    style.textContent = [
      "#" + TOOLBAR_ID + "{position:fixed;right:8px;top:45%;transform:translateY(-50%);z-index:9999;display:flex;flex-direction:column;gap:6px;align-items:flex-end}",
      "#" + TOOLBAR_ID + " .krun-docs-btn{min-width:56px;padding:6px 8px;font-size:12px;line-height:1;color:#3b4151;background:rgba(255,255,255,.92);border:1px solid #d9d9d9;border-radius:4px;cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,.12);transition:all .2s;font-family:sans-serif}",
      "#" + TOOLBAR_ID + " .krun-docs-btn:hover{color:#fff;background:#4990e2;border-color:#4990e2}",
      "#" + TOOLBAR_ID + " .krun-docs-toggle{min-width:28px}",
      "#" + TOOLBAR_ID + "." + TOOLBAR_COLLAPSED_CLASS + " .krun-docs-btn:not(.krun-docs-toggle){display:none}",
    ].join("");
    return style;
  }

  function mountToolbar() {
    // 防重复注入(脚本被意外引入两次时保持幂等)
    if (document.getElementById(TOOLBAR_ID)) {
      return;
    }
    document.body.appendChild(buildToolbarStyle());
    document.body.appendChild(buildToolbar());
  }

  mountToolbar();
})();

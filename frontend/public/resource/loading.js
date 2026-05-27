/**
 * 初始化加载效果的svg格式logo
 * @param {string} id - 元素id
 */
function initSvgLogo(id) {
    const svgStr = `<?xml version="1.0" encoding="UTF-8"?> <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 500" width="100%" height="100%"> <title>Krun Logo</title> <path fill="currentColor" fill-rule="nonzero" shape-rendering="geometricPrecision" style="stroke-linejoin: miter; stroke-linecap: butt;" d="M150.6,68.9 L470.6,68.9 L493.3,83.3 L497.8,92.2 L497.8,120.0 L393.9,325.6 L295.1,262.2 L238.5,299.6 L287.8,355.1 L466.8,355.7 L404.4,393.3 L388.7,404.6 L368.3,422.8 L349.4,430.0 L28.9,430.0 L5.6,413.3 L1.7,382.8 L83.3,171.1 L130.0,199.2 L145.4,212.2 L112.8,355.6 L192.8,356.1 L207.2,286.7 L220.0,279.4 L238.3,299.4 L390.6,149.4 L399.0,135.6 L297.2,145.6 L218.9,226.7 L234.4,145.6 L6.8,166.4 L62.2,131.1 L122.8,82.8 L150.6,68.9Z"/></svg>`
    const appEl = document.querySelector(id)
    const div = document.createElement('div')
    div.innerHTML = svgStr
    if (appEl) {
        appEl.appendChild(div)
    }
}

function addThemeColorCssVars() {
    const key = '__THEME_COLOR__'
    const defaultColor = '#F4511E'
    const themeColor = window.localStorage.getItem(key) || defaultColor
    const cssVars = `--primary-color: ${themeColor}`
    document.documentElement.style.cssText = cssVars
}

addThemeColorCssVars()

initSvgLogo('#loadingLogo')

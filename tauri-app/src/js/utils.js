// Shared utility: resize Tauri window to fit content

/**
 * Resize the current Tauri window to fit the content of the given element.
 * @param {string} elementId - The id of the root app element
 * @param {object} [options]
 * @param {boolean} [options.center] - If true, center on screen instead of bottom-right
 */
export function resizeToFit(elementId, options) {
    var opts = options || {};
    var win = window.__TAURI__.window.getCurrentWindow();

    // 关键：窗口不可见时不要 setSize/setPosition。
    // 后台刷新（usage-updated）每分钟触发一次，若对隐藏的 webview 窗口
    // 调整尺寸，会在 Windows 上触发 webview 渲染窗口的 创建→显示→隐藏，
    // 表现为空白窗口反复闪动。隐藏时直接跳过。
    win.isVisible().then(function (visible) {
        if (!visible) return;
        performResize(elementId, win, opts);
    }).catch(function () {
        performResize(elementId, win, opts);
    });
}

function performResize(elementId, win, opts) {
    requestAnimationFrame(function () {
        requestAnimationFrame(function () {
            var appEl = document.getElementById(elementId);
            if (!appEl) return;
            var rect = appEl.getBoundingClientRect();
            var width = Math.max(Math.ceil(rect.width), 100);
            var height = Math.max(Math.ceil(rect.height), 60);

            var mod = window.__TAURI__.dpi || window.__TAURI__.window;

            var sizeObj = mod.LogicalSize
                ? new mod.LogicalSize(width, height)
                : { type: 'Logical', width: width, height: height };

            win.setSize(sizeObj).then(function () {
                return win.primaryMonitor();
            }).then(function (monitor) {
                if (monitor) {
                    var sW = monitor.size.width / monitor.scaleFactor;
                    var sH = monitor.size.height / monitor.scaleFactor;
                    var x, y;
                    if (opts.center) {
                        x = Math.round(sW / 2 - width / 2);
                        y = Math.round(sH / 2 - height / 2);
                    } else {
                        x = Math.round(sW - width - 16);
                        y = Math.round(sH - height - 60);
                    }
                    var posObj = mod.LogicalPosition
                        ? new mod.LogicalPosition(Math.max(x, 0), Math.max(y, 0))
                        : { type: 'Logical', x: Math.max(x, 0), y: Math.max(y, 0) };
                    return win.setPosition(posObj);
                }
            }).catch(function (e) {
                console.error('resize failed:', e);
            });
        });
    });
}

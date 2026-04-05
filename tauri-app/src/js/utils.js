// Shared utility: resize Tauri window to fit content

/**
 * Resize the current Tauri window to fit the content of the given element.
 * @param {string} elementId - The id of the root app element
 * @param {object} [options]
 * @param {boolean} [options.center] - If true, center on screen instead of bottom-right
 */
export function resizeToFit(elementId, options) {
    var opts = options || {};
    requestAnimationFrame(function() {
        requestAnimationFrame(function() {
            var appEl = document.getElementById(elementId);
            if (!appEl) return;
            var rect = appEl.getBoundingClientRect();
            var width = Math.max(Math.ceil(rect.width), 100);
            var height = Math.max(Math.ceil(rect.height), 60);

            var win = window.__TAURI__.window.getCurrentWindow();
            var mod = window.__TAURI__.dpi || window.__TAURI__.window;

            var sizeObj = mod.LogicalSize
                ? new mod.LogicalSize(width, height)
                : { type: 'Logical', width: width, height: height };

            win.setSize(sizeObj).then(function() {
                return win.primaryMonitor();
            }).then(function(monitor) {
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
            }).catch(function(e) {
                console.error('resize failed:', e);
            });
        });
    });
}

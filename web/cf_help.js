import { app } from "../../../scripts/app.js";

function getLocale() {
    const locale = localStorage['AGL.Locale'] || localStorage['Comfy.Settings.AGL.Locale'] || 'en-US';
    return locale.startsWith('zh') ? 'zh' : 'en';
}

const nodeHelpCache = {};

function loadHelpText(nodeName, lang) {
    const key = `${nodeName}.${lang}`;
    if (nodeHelpCache[key] !== undefined) return Promise.resolve(nodeHelpCache[key]);
    return fetch(`./help/${nodeName}.${lang}.md?_=${Date.now()}`)
        .then(r => r.ok ? r.text() : "")
        .then(t => { nodeHelpCache[key] = t || `Help not available for ${nodeName} (${lang})`; return nodeHelpCache[key]; })
        .catch(() => { nodeHelpCache[key] = `Help not available for ${nodeName} (${lang})`; return nodeHelpCache[key]; });
}

function showPopup(node, docText) {
    closePopup();
    if (!docText) return;

    const popup = document.createElement("div");
    popup.className = "cf-help-popup";
    Object.assign(popup.style, {
        position: "absolute", zIndex: "100000",
        backgroundColor: "#1a1a2e", color: "#ccc",
        borderRadius: "10px", padding: "16px 20px",
        maxWidth: "420px", maxHeight: "340px",
        overflow: "auto", fontSize: "12px", lineHeight: "1.5",
        whiteSpace: "pre-wrap", fontFamily: "monospace",
        boxShadow: "0 6px 24px rgba(0,0,0,0.6)",
    });
    popup.textContent = docText;

    const closeBtn = document.createElement("button");
    closeBtn.textContent = "✖";
    Object.assign(closeBtn.style, {
        position: "absolute", top: "4px", right: "8px",
        background: "none", border: "none", color: "#888", fontSize: "14px", cursor: "pointer",
    });
    closeBtn.onclick = (e) => { e.stopPropagation(); closePopup(); };
    popup.appendChild(closeBtn);

    document.body.appendChild(popup);
    window._cfHelpPopup = popup;
    window._cfHelpPopupNode = node;

    updatePopupPosition();
    window._cfHelpPosTimer = setInterval(updatePopupPosition, 100);
}

function updatePopupPosition() {
    const popup = window._cfHelpPopup;
    const node = window._cfHelpPopupNode;
    if (!popup || !node) return;

    const el = node.element;
    if (!el) return;
    const nodeRect = el.getBoundingClientRect();
    const popupW = popup.offsetWidth;
    const popupH = popup.offsetHeight;
    const vw = window.innerWidth;

    let left = nodeRect.right + 10;
    if (left + popupW > vw - 10) left = nodeRect.left - popupW - 10;
    if (left < 10) left = 10;

    let top = nodeRect.top;
    if (top + popupH > window.innerHeight - 10) top = window.innerHeight - popupH - 10;
    if (top < 10) top = 10;

    popup.style.left = left + "px";
    popup.style.top = top + "px";
}

function closePopup() {
    const popup = window._cfHelpPopup;
    if (popup) { popup.remove(); window._cfHelpPopup = null; }
    if (window._cfHelpPosTimer) { clearInterval(window._cfHelpPosTimer); window._cfHelpPosTimer = null; }
}

document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closePopup();
});

const CF_NODES = new Set([
    "CF_BatchImageLoader", "CF_BatchImageManager",
    "CF_BatchVideoLoader", "CF_BatchVideoManager",
    "CF_SimpleAudioCutter", "CF_QwenImageEditEnhanced",
    "CF_UniversalCalculator",
]);

app.registerExtension({
    name: "CF_HelpButton",
    async beforeRegisterNodeDef(nodeType) {
        if (!CF_NODES.has(nodeType.comfyClass)) return;

        const iconSize = 14;
        const iconMargin = 4;

        const origOnDrawForeground = nodeType.prototype.onDrawForeground;
        nodeType.prototype.onDrawForeground = function (ctx) {
            const r = origOnDrawForeground?.apply(this, arguments);
            if (this.flags.collapsed) return r;

            const x = this.size[0] - iconSize - iconMargin;

            ctx.save();
            ctx.translate(x - 2, iconSize - 34);
            ctx.scale(iconSize / 32, iconSize / 32);
            ctx.strokeStyle = "rgba(255,255,255,0.3)";
            ctx.lineCap = "round";
            ctx.lineJoin = "round";
            ctx.lineWidth = 2.4;
            ctx.font = "bold 36px monospace";
            ctx.fillStyle = "#e69138";
            ctx.fillText("?", 0, 24);
            ctx.restore();
            return r;
        };

        const origOnMouseDown = nodeType.prototype.onMouseDown;
        nodeType.prototype.onMouseDown = function (e, localPos, canvas) {
            const r = origOnMouseDown?.apply(this, arguments);
            const iconX = this.size[0] - iconSize - iconMargin;
            const iconY = iconSize - 34;
            if (
                localPos[0] > iconX &&
                localPos[0] < iconX + iconSize &&
                localPos[1] > iconY &&
                localPos[1] < iconY + iconSize
            ) {
                const lang = getLocale();
                const nodeName = this.constructor?.type || "";
                loadHelpText(nodeName, lang).then(text => {
                    if (text && !text.startsWith("Help not available")) {
                        showPopup(this, text);
                    }
                });
                return true;
            }
            return r;
        };
    },
});

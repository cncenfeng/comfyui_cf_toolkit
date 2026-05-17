import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

const TARGET_CLASS = "CF_BatchImageManager";
const FIXED_NODE_HEIGHT = 200; // 固定节点高度

let sortable = null;

async function fetchFileList(subdir) {
    const resp = await fetch(api.apiURL(`/batchimage/output/list?subdir=${encodeURIComponent(subdir)}`));
    if (!resp.ok) return [];
    const data = await resp.json();
    return data.files;
}

async function applySorting(subdir, orderedFilenames) {
    await fetch(api.apiURL("/batchimage/output/apply"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subdir, ordered_filenames: orderedFilenames })
    });
}

function addUI(node) {
    if (node._uiAdded) return;
    node._uiAdded = true;

    const subdirWidget = node.widgets.find(w => w.name === "子目录");
    if (!subdirWidget) {
        console.error("[BatchImageManager] 未找到子目录控件");
        return;
    }

    // ---------- 创建管理面板容器 ----------
    const container = document.createElement("div");
    container.style.margin = "0";
    container.style.padding = "4px";
    container.style.width = "100%";
    container.style.height = "100%";           // 让容器填充整个 widget 区域
    container.style.boxSizing = "border-box";
    container.style.display = "flex";
    container.style.flexDirection = "column";

    const domWidget = node.addDOMWidget("image_manager_ui", "image_manager_ui", container, { serialize: false });

    // ★ computeSize 返回固定高度，确保节点不会自己变化
    if (domWidget) {
        domWidget.computeSize = () => {
            const w = node.size ? node.size[0] : 300;
            return [w, FIXED_NODE_HEIGHT];
        };
    }

    // 设置一个合理的初始节点大小
    if (node.setSize && node.size) {
        node.setSize([node.size[0] || 500, FIXED_NODE_HEIGHT]);
    }

    const btnDiv = document.createElement("div");
    btnDiv.style.display = "flex";
    btnDiv.style.gap = "8px";
    btnDiv.style.marginBottom = "8px";
    container.appendChild(btnDiv);

    const refreshBtn = document.createElement("button");
    refreshBtn.textContent = "🔄 刷新";
    const applyBtn = document.createElement("button");
    applyBtn.textContent = "✅ 应用排序";
    btnDiv.appendChild(refreshBtn);
    btnDiv.appendChild(applyBtn);

    // ---------- 图片列表区域（改为水平滚动）----------
    const listDiv = document.createElement("div");
    listDiv.style.display = "flex";
    listDiv.style.flexWrap = "nowrap";        // 不换行，水平排列
    listDiv.style.gap = "8px";
    listDiv.style.overflowX = "auto";         // 水平滚动条
    listDiv.style.overflowY = "hidden";       // 禁止垂直滚动
    listDiv.style.padding = "4px";
    listDiv.style.border = "1px solid #666";
    listDiv.style.flex = "1";                 // 占据剩余高度
    listDiv.style.alignItems = "flex-start";
    container.appendChild(listDiv);

    // ---------- 放大预览浮层（全局唯一）----------
    let overlay = null;
    function createOverlay() {
        if (overlay) return overlay;
        overlay = document.createElement("div");
        overlay.style.position = "fixed";
        overlay.style.top = "0";
        overlay.style.left = "0";
        overlay.style.width = "100vw";
        overlay.style.height = "100vh";
        overlay.style.backgroundColor = "rgba(0,0,0,0.85)";
        overlay.style.display = "none";
        overlay.style.alignItems = "center";
        overlay.style.justifyContent = "center";
        overlay.style.zIndex = "99999";
        overlay.style.cursor = "zoom-out";

        const largeImg = document.createElement("img");
        largeImg.style.maxWidth = "90vw";
        largeImg.style.maxHeight = "90vh";
        largeImg.style.objectFit = "contain";
        largeImg.style.borderRadius = "8px";
        overlay.appendChild(largeImg);

        // 点击浮层关闭
        overlay.addEventListener("click", () => {
            overlay.style.display = "none";
        });
        // ESC 关闭
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && overlay.style.display === "flex") {
                overlay.style.display = "none";
            }
        });

        document.body.appendChild(overlay);
        return overlay;
    }

    function showLargeImage(src) {
        const ov = createOverlay();
        const img = ov.querySelector("img");
        img.src = src;
        ov.style.display = "flex";
    }

    // ---------- 更新列表逻辑 ----------
    async function updateList() {
        const files = await fetchFileList(subdirWidget.value);
        listDiv.innerHTML = "";
        for (const file of files) {
            const item = document.createElement("div");
            item.className = "image-item";
            item.setAttribute("data-filename", file);
            item.style.position = "relative";
            item.style.height = "120px";
            item.style.margin = "4px";
            item.style.cursor = "grab";
            item.style.backgroundColor = "#222";
            item.style.borderRadius = "6px";
            item.style.overflow = "hidden";
            item.style.flexShrink = "0";       // 防止被压缩

            const img = document.createElement("img");
            const imgSrc = api.apiURL(`/batchimage/output/preview?subdir=${encodeURIComponent(subdirWidget.value)}&filename=${encodeURIComponent(file)}&_=${Date.now()}`);
            img.src = imgSrc;
            img.style.width = "100%";
            img.style.height = "100%";
            img.style.objectFit = "cover";
            img.style.display = "block";
            item.appendChild(img);

            const nameSpan = document.createElement("div");
            nameSpan.textContent = file;
            nameSpan.style.position = "absolute";
            nameSpan.style.bottom = "0";
            nameSpan.style.left = "0";
            nameSpan.style.right = "0";
            nameSpan.style.backgroundColor = "rgba(0,0,0,0.6)";
            nameSpan.style.color = "white";
            nameSpan.style.fontSize = "10px";
            nameSpan.style.textAlign = "center";
            nameSpan.style.padding = "2px";
            item.appendChild(nameSpan);

            const delBtn = document.createElement("button");
            delBtn.textContent = "✖";
            delBtn.style.position = "absolute";
            delBtn.style.top = "2px";
            delBtn.style.right = "2px";
            delBtn.style.backgroundColor = "rgba(0,0,0,0.6)";
            delBtn.style.color = "white";
            delBtn.style.border = "none";
            delBtn.style.borderRadius = "50%";
            delBtn.style.width = "20px";
            delBtn.style.height = "20px";
            delBtn.style.cursor = "pointer";
            delBtn.onclick = (e) => {
                e.stopPropagation();
                item.remove();
            };
            item.appendChild(delBtn);

            // ★ 点击图片放大（但不影响删除按钮）
            item.addEventListener("click", (e) => {
                // 如果点的是删除按钮或子元素，不触发放大
                if (e.target === delBtn || delBtn.contains(e.target)) return;
                showLargeImage(imgSrc);
            });

            listDiv.appendChild(item);
        }

        if (!window.Sortable) {
            await new Promise((resolve) => {
                const script = document.createElement("script");
                script.src = "./Sortable.min.js";
                script.onload = resolve;
                document.head.appendChild(script);
            });
        }
        if (sortable) sortable.destroy();
        sortable = new window.Sortable(listDiv, {
            animation: 150,
            handle: ".image-item",
            ghostClass: "sortable-ghost",
            // Sortable 默认竖向，我们要改为横向拖拽
            direction: "horizontal",
        });
    }

    // 自动刷新事件
    api.addEventListener("batchimage_manager_refresh", (event) => {
        if (event.detail.subdir === subdirWidget.value) {
            updateList();
        }
    });

    refreshBtn.onclick = () => {
        updateList();
        console.log("[BatchImageManager] 列表已刷新");
    };

    applyBtn.onclick = async () => {
        const items = listDiv.querySelectorAll(".image-item");
        const ordered = Array.from(items).map(item => item.getAttribute("data-filename"));
        try {
            await applySorting(subdirWidget.value, ordered);
            await updateList();
            console.log("[BatchImageManager] 排序已应用（含删除）");
        } catch(err) {
            console.error("[BatchImageManager] 应用失败:", err.message);
        }
    };

    subdirWidget.callback = (v) => {
        updateList();
    };
    updateList();
}

app.registerExtension({
    name: "BatchImageManager",
    async nodeCreated(node) {
        if (node.comfyClass === TARGET_CLASS) {
            setTimeout(() => addUI(node), 100);
        }
    },
});
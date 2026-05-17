import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

const TARGET_CLASS = "CF_BatchImageLoader";
const FIXED_NODE_HEIGHT = 200;

let sortable = null;

async function fetchFileList(subdir) {
    const resp = await fetch(api.apiURL(`/batchimage/list?subdir=${encodeURIComponent(subdir)}`));
    if (!resp.ok) return [];
    const data = await resp.json();
    return data.files;
}

async function getNextNumber(subdir) {
    const resp = await fetch(api.apiURL(`/batchimage/next_number?subdir=${encodeURIComponent(subdir)}`));
    if (!resp.ok) throw new Error("获取序号失败");
    const data = await resp.json();
    return data.next_num;
}

async function uploadFiles(files, subdir, onProgress) {
    let nextNum = await getNextNumber(subdir);
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const ext = file.name.split('.').pop();
        const newName = String(nextNum + i).padStart(3, '0') + '.' + ext;
        const renamedFile = new File([file], newName, { type: file.type });
        const formData = new FormData();
        formData.append("image", renamedFile);
        formData.append("subfolder", subdir);
        formData.append("overwrite", "false");
        await new Promise((resolve, reject) => {
            const req = new XMLHttpRequest();
            req.upload.onprogress = (e) => onProgress?.(i, e.loaded / e.total);
            req.onload = () => {
                if (req.status === 200) resolve();
                else reject(new Error(`上传失败: ${req.status}`));
            };
            req.onerror = () => reject(new Error("网络错误"));
            req.open("POST", api.apiURL("/upload/image"), true);
            req.send(formData);
        });
    }
}

async function applyChanges(subdir, orderedFilenames) {
    const resp = await fetch(api.apiURL("/batchimage/apply"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subdir, ordered_filenames: orderedFilenames })
    });
    if (!resp.ok) throw new Error("应用更改失败");
    const data = await resp.json();
    return data.files;
}

function addUI(node) {
    if (node._uiAdded) return;
    node._uiAdded = true;

    // 隐藏的排除文件 widget（由前端自动管理）
    const excludeWidget = node.widgets.find(w => w.name === "排除文件");
    let hiddenFiles = new Set();  // 当前被排除的文件名
    if (excludeWidget) {
        hiddenFiles = new Set(excludeWidget.value.split(",").filter(Boolean));
    }

    // 隐藏刷新触发器
    const refreshTrigger = node.widgets.find(w => w.name === "刷新触发器");
    if (refreshTrigger) {
        const tryHide = (el) => {
            if (!el) return;
            let target = el;
            while (target && target !== node.element && !target.classList?.contains("comfy-widget")) {
                target = target.parentElement;
            }
            if (target && target !== node.element) {
                target.style.display = "none";
            } else {
                if (el.style) el.style.display = "none";
            }
        };
        tryHide(refreshTrigger.element);
        if (refreshTrigger.inputEl) tryHide(refreshTrigger.inputEl);
        if (refreshTrigger.element) {
            let parent = refreshTrigger.element.parentElement;
            while (parent && parent !== node.element && !parent.classList?.contains("comfy-widget")) {
                parent = parent.parentElement;
            }
            if (parent && parent !== node.element) parent.style.display = "none";
        }
    }

    const subdirWidget = node.widgets.find(w => w.name === "子目录");
    if (!subdirWidget) {
        console.error("未找到子目录控件");
        return;
    }

    // ---------- 创建管理面板容器 ----------
    const container = document.createElement("div");
    container.style.margin = "0";
    container.style.padding = "4px";
    container.style.width = "100%";
    container.style.height = "100%";
    container.style.boxSizing = "border-box";
    container.style.display = "flex";
    container.style.flexDirection = "column";

    const domWidget = node.addDOMWidget("image_ui", "image_ui", container, { serialize: false });

    if (domWidget) {
        domWidget.computeSize = () => {
            const w = node.size ? node.size[0] : 300;
            return [w, FIXED_NODE_HEIGHT];
        };
    }
    if (node.setSize && node.size) {
        node.setSize([node.size[0] || 500, FIXED_NODE_HEIGHT]);
    }

    const btnDiv = document.createElement("div");
    btnDiv.style.display = "flex";
    btnDiv.style.gap = "8px";
    btnDiv.style.marginBottom = "8px";
    container.appendChild(btnDiv);

    const uploadBtn = document.createElement("button");
    uploadBtn.textContent = "📤 上传图片";
    const refreshBtn = document.createElement("button");
    refreshBtn.textContent = "🔄 刷新";
    const applyBtn = document.createElement("button");
    applyBtn.textContent = "✅ 应用排序";
    btnDiv.appendChild(uploadBtn);
    btnDiv.appendChild(refreshBtn);
    btnDiv.appendChild(applyBtn);

    // ---------- 图片列表区域（水平滚动）----------
    const listDiv = document.createElement("div");
    listDiv.style.display = "flex";
    listDiv.style.flexWrap = "nowrap";
    listDiv.style.gap = "8px";
    listDiv.style.overflowX = "auto";
    listDiv.style.overflowY = "hidden";
    listDiv.style.padding = "4px";
    listDiv.style.border = "1px solid #666";
    listDiv.style.flex = "1";
    listDiv.style.alignItems = "flex-start";
    container.appendChild(listDiv);

    // ---------- 放大预览浮层 ----------
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

        overlay.addEventListener("click", () => {
            overlay.style.display = "none";
        });
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

    // 更新隐藏参数并触发刷新
    function updateExcludeWidget() {
        if (excludeWidget) {
            excludeWidget.value = Array.from(hiddenFiles).join(",");
            if (excludeWidget.callback) excludeWidget.callback(excludeWidget.value);
        }
        // 同时切换触发器，强制重新计算
        if (refreshTrigger) {
            refreshTrigger.value = !refreshTrigger.value;
            if (refreshTrigger.callback) refreshTrigger.callback(refreshTrigger.value);
        }
    }

    // ---------- 更新列表逻辑 ----------
    async function updateList() {
        const files = await fetchFileList(subdirWidget.value);
        listDiv.innerHTML = "";
        for (const file of files) {
            const isHidden = hiddenFiles.has(file);
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
            item.style.flexShrink = "0";
            // 如果被排除，降低透明度提示
            item.style.opacity = isHidden ? "0.45" : "1";
            item.style.transition = "opacity 0.15s";

            const img = document.createElement("img");
            const imgSrc = api.apiURL(`/batchimage/preview?subdir=${encodeURIComponent(subdirWidget.value)}&filename=${encodeURIComponent(file)}&_=${Date.now()}`);
            img.src = imgSrc;
            img.style.width = "100%";
            img.style.height = "100%";
            img.style.objectFit = "cover";
            img.style.display = "block";
            item.appendChild(img);

            // 文件名（留出右下角空间）
            const nameSpan = document.createElement("div");
            nameSpan.textContent = file;
            nameSpan.style.position = "absolute";
            nameSpan.style.bottom = "0";
            nameSpan.style.left = "0";
            nameSpan.style.right = "22px";  // 留出眼睛按钮的空间
            nameSpan.style.backgroundColor = "rgba(0,0,0,0.6)";
            nameSpan.style.color = "white";
            nameSpan.style.fontSize = "10px";
            nameSpan.style.textAlign = "center";
            nameSpan.style.padding = "2px";
            nameSpan.style.whiteSpace = "nowrap";
            nameSpan.style.overflow = "hidden";
            nameSpan.style.textOverflow = "ellipsis";
            item.appendChild(nameSpan);

            // 删除按钮（右上角）
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

            // 眼睛按钮（右下角）
            const eyeBtn = document.createElement("button");
            eyeBtn.textContent = isHidden ? "🙈" : "👁️";
            eyeBtn.title = isHidden ? "点击包含此图片" : "点击排除此图片";
            eyeBtn.style.position = "absolute";
            eyeBtn.style.bottom = "2px";
            eyeBtn.style.right = "2px";
            eyeBtn.style.backgroundColor = "rgba(0,0,0,0.5)";
            eyeBtn.style.color = "white";
            eyeBtn.style.border = "none";
            eyeBtn.style.borderRadius = "50%";
            eyeBtn.style.width = "18px";
            eyeBtn.style.height = "18px";
            eyeBtn.style.fontSize = "12px";
            eyeBtn.style.cursor = "pointer";
            eyeBtn.style.display = "flex";
            eyeBtn.style.alignItems = "center";
            eyeBtn.style.justifyContent = "center";
            eyeBtn.style.padding = "0";
            eyeBtn.style.lineHeight = "1";
            eyeBtn.onclick = (e) => {
                e.stopPropagation();
                if (hiddenFiles.has(file)) {
                    hiddenFiles.delete(file);
                } else {
                    hiddenFiles.add(file);
                }
                // 更新 UI 状态（不需要重新拉取列表）
                const newHidden = hiddenFiles.has(file);
                item.style.opacity = newHidden ? "0.45" : "1";
                eyeBtn.textContent = newHidden ? "🙈" : "👁️";
                eyeBtn.title = newHidden ? "点击包含此图片" : "点击排除此图片";
                // 更新隐藏参数并触发刷新
                updateExcludeWidget();
            };
            item.appendChild(eyeBtn);

            // 点击图片放大（不干扰按钮）
            item.addEventListener("click", (e) => {
                if (e.target === delBtn || delBtn.contains(e.target)) return;
                if (e.target === eyeBtn || eyeBtn.contains(e.target)) return;
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
            direction: "horizontal",
        });
    }

    uploadBtn.onclick = () => {
        const input = document.createElement("input");
        input.type = "file";
        input.multiple = true;
        input.accept = "image/*";
        input.onchange = async () => {
            if (!input.files.length) return;
            const files = Array.from(input.files);
            const originalText = uploadBtn.textContent;
            uploadBtn.textContent = "上传中...";
            uploadBtn.disabled = true;
            try {
                await uploadFiles(files, subdirWidget.value, (idx, prog) => {
                    uploadBtn.textContent = `上传中 ${idx+1}/${files.length} ${Math.round(prog*100)}%`;
                });
                await updateList();
                // 上传后新图片默认可见（不在 hiddenFiles 里），但需要更新 exclude widget
                updateExcludeWidget();
                console.log("[BatchImageLoader] 上传完成");
            } catch(err) {
                console.error("[BatchImageLoader] 上传失败:", err.message);
            } finally {
                uploadBtn.textContent = originalText;
                uploadBtn.disabled = false;
            }
        };
        input.click();
    };

    refreshBtn.onclick = async () => {
        await updateList();
        console.log("[BatchImageLoader] 列表已刷新");
    };

    applyBtn.onclick = async () => {
        const items = listDiv.querySelectorAll(".image-item");
        const ordered = Array.from(items).map(item => item.getAttribute("data-filename"));
        try {
            await applyChanges(subdirWidget.value, ordered);
            await updateList();
            // 排序后 hiddenFiles 不变（仍然排除那些文件），需要同步排除参数并触发刷新
            updateExcludeWidget();
            console.log("[BatchImageLoader] 排序已应用");
        } catch(err) {
            console.error("[BatchImageLoader] 应用失败:", err.message);
        }
    };

    const origCallback = subdirWidget.callback;
    subdirWidget.callback = function(v) {
        if (origCallback) origCallback(v);
        updateList();
    };
    updateList();
}

app.registerExtension({
    name: "BatchImageLoader",
    async nodeCreated(node) {
        if (node.comfyClass === TARGET_CLASS) {
            setTimeout(() => addUI(node), 100);
        }
    },
});
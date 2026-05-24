import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

const TARGET_IMAGE_LOADER  = "CF_BatchImageLoader";
const TARGET_IMAGE_MANAGER = "CF_BatchImageManager";
const TARGET_VIDEO_LOADER  = "CF_BatchVideoLoader";
const TARGET_VIDEO_MANAGER = "CF_BatchVideoManager";
const FIXED_HEIGHT = 200;

let sortable = null;

async function fetchFileList(routeKey, subdir) {
    const resp = await fetch(api.apiURL(`/cf_media/${routeKey}/list?subdir=${encodeURIComponent(subdir)}`));
    if (!resp.ok) return [];
    const data = await resp.json();
    return data.files || [];
}

async function getNextNumber(routeKey, subdir) {
    const resp = await fetch(api.apiURL(`/cf_media/${routeKey}/next_number?subdir=${encodeURIComponent(subdir)}`));
    if (!resp.ok) return 0;
    const data = await resp.json();
    return data.next_num;
}

async function uploadFiles(files, subdir, onProgress) {
    const nextNum = await getNextNumber("image_input", subdir);
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const ext = file.name.split(".").pop();
        const newName = String(nextNum + i).padStart(3, "0") + "." + ext;
        const renamedFile = new File([file], newName, { type: file.type });
        const formData = new FormData();
        formData.append("image", renamedFile);
        formData.append("subfolder", subdir);
        formData.append("overwrite", "false");
        await new Promise((resolve, reject) => {
            const req = new XMLHttpRequest();
            req.upload.onprogress = (e) => onProgress?.(i, e.loaded / e.total);
            req.onload = () => { req.status === 200 ? resolve() : reject(new Error(`Upload failed: ${req.status}`)); };
            req.onerror = () => reject(new Error("Network error"));
            req.open("POST", api.apiURL("/upload/image"), true);
            req.send(formData);
        });
    }
}

async function applyOrdering(routeKey, subdir, orderedFilenames) {
    const resp = await fetch(api.apiURL(`/cf_media/${routeKey}/apply`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subdir, ordered_filenames: orderedFilenames }),
    });
    if (!resp.ok) throw new Error("Apply failed");
    const data = await resp.json();
    return data.files || [];
}

function createOverlay() {
    if (createOverlay._instance) return createOverlay._instance;

    const overlay = document.createElement("div");
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

    const prevBtn = document.createElement("button");
    prevBtn.textContent = "‹";
    Object.assign(prevBtn.style, {
        position: "absolute", left: "16px", top: "50%", transform: "translateY(-50%)",
        fontSize: "48px", lineHeight: "1", color: "white", backgroundColor: "rgba(0,0,0,0.4)",
        border: "none", borderRadius: "6px", cursor: "pointer", padding: "8px 16px",
        zIndex: "100000",
    });
    prevBtn.addEventListener("click", (e) => { e.stopPropagation(); overlay.showPrev(); });
    prevBtn.addEventListener("mouseenter", () => { prevBtn.style.backgroundColor = "rgba(255,255,255,0.25)"; });
    prevBtn.addEventListener("mouseleave", () => { prevBtn.style.backgroundColor = "rgba(0,0,0,0.4)"; });
    overlay.appendChild(prevBtn);

    const nextBtn = document.createElement("button");
    nextBtn.textContent = "›";
    Object.assign(nextBtn.style, {
        position: "absolute", right: "16px", top: "50%", transform: "translateY(-50%)",
        fontSize: "48px", lineHeight: "1", color: "white", backgroundColor: "rgba(0,0,0,0.4)",
        border: "none", borderRadius: "6px", cursor: "pointer", padding: "8px 16px",
        zIndex: "100000",
    });
    nextBtn.addEventListener("click", (e) => { e.stopPropagation(); overlay.showNext(); });
    nextBtn.addEventListener("mouseenter", () => { nextBtn.style.backgroundColor = "rgba(255,255,255,0.25)"; });
    nextBtn.addEventListener("mouseleave", () => { nextBtn.style.backgroundColor = "rgba(0,0,0,0.4)"; });
    overlay.appendChild(nextBtn);

    overlay.addEventListener("click", () => { overlay.style.display = "none"; });
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && overlay.style.display === "flex") {
            overlay.style.display = "none";
        }
    });
    document.body.appendChild(overlay);

    overlay._currentIndex = -1;
    overlay._items = [];
    overlay._routeKey = "";
    overlay._subdir = "";

    overlay.showImage = function (index, items, routeKey, subdir) {
        if (index < 0 || index >= items.length) return;
        this._currentIndex = index;
        this._items = items;
        this._routeKey = routeKey;
        this._subdir = subdir;
        const src = api.apiURL(`/cf_media/${routeKey}/preview?subdir=${encodeURIComponent(subdir)}&filename=${encodeURIComponent(items[index])}&_=${Date.now()}`);
        largeImg.src = src;
        this.style.display = "flex";
    };

    overlay.showNext = function () {
        if (this._items.length === 0) return;
        const idx = (this._currentIndex + 1) % this._items.length;
        this.showImage(idx, this._items, this._routeKey, this._subdir);
    };

    overlay.showPrev = function () {
        if (this._items.length === 0) return;
        const idx = (this._currentIndex - 1 + this._items.length) % this._items.length;
        this.showImage(idx, this._items, this._routeKey, this._subdir);
    };

    document.addEventListener("keydown", (e) => {
        if (overlay.style.display !== "flex") return;
        if (e.key === "ArrowRight") overlay.showNext();
        if (e.key === "ArrowLeft") overlay.showPrev();
    });

    createOverlay._instance = overlay;
    return overlay;
}

function addUI(node, routeKey, isVideo) {
    if (node._uiAdded) return;
    node._uiAdded = true;

    const excludeWidget = !isVideo ? node.widgets.find(w => w.name === "exclude_files") : null;
    let hiddenFiles = new Set();
    if (excludeWidget) {
        hiddenFiles = new Set(excludeWidget.value.split(",").filter(Boolean));
    }

    const subdirWidget = node.widgets.find(w => w.name === "subdirectory");
    if (!subdirWidget) return;

    const container = document.createElement("div");
    Object.assign(container.style, {
        margin: "0", padding: "4px", width: "100%", height: "100%",
        boxSizing: "border-box", display: "flex", flexDirection: "column",
    });

    const domWidget = node.addDOMWidget("cf_batch_media_ui", "cf_batch_media_ui", container, { serialize: false });
    if (domWidget) domWidget.computeSize = () => [node.size?.[0] || 300, FIXED_HEIGHT];
    if (node.setSize) node.setSize([node.size?.[0] || 500, FIXED_HEIGHT]);

    // --- Button bar ---
    const btnDiv = document.createElement("div");
    btnDiv.style.cssText = "display:flex;gap:8px;margin-bottom:8px;flex-wrap:wrap;";
    container.appendChild(btnDiv);

    const uploadBtn = document.createElement("button");
    uploadBtn.textContent = isVideo ? "📤 上传媒体" : "📤 上传图片";
    if (routeKey.endsWith("_output")) {
        uploadBtn.style.display = "none";
    }
    const refreshBtn = document.createElement("button");
    refreshBtn.textContent = "🔄 刷新";
    const applyBtn = document.createElement("button");
    applyBtn.textContent = "✅ 应用排序";
    btnDiv.appendChild(uploadBtn);
    btnDiv.appendChild(refreshBtn);
    btnDiv.appendChild(applyBtn);

    // --- Thumbnail list (horizontal scroll) ---
    const listDiv = document.createElement("div");
    listDiv.style.cssText = "display:flex;flex-wrap:nowrap;gap:8px;overflow-x:auto;overflow-y:hidden;padding:4px;border:1px solid #666;flex:1;align-items:flex-start;";
    container.appendChild(listDiv);

    // --- Update exclude widget ---
    function updateExcludeWidget() {
        if (excludeWidget) {
            excludeWidget.value = Array.from(hiddenFiles).join(",");
            excludeWidget.callback?.(excludeWidget.value);
        }
    }

    // --- Refresh list ---
    async function updateList() {
        const files = await fetchFileList(routeKey, subdirWidget.value);
        listDiv.innerHTML = "";

        const overlay = createOverlay();

        for (const file of files) {
            const isHidden = !isVideo && hiddenFiles.has(file);
            const item = document.createElement("div");
            item.className = "media-item";
            item.setAttribute("data-filename", file);
            Object.assign(item.style, {
                position: "relative", height: "120px", margin: "4px",
                cursor: "grab", backgroundColor: "#222", borderRadius: "6px",
                overflow: "hidden", flexShrink: "0",
                opacity: isHidden ? "0.45" : "1", transition: "opacity 0.15s",
            });

            const img = document.createElement("img");
            img.src = api.apiURL(`/cf_media/${routeKey}/preview?subdir=${encodeURIComponent(subdirWidget.value)}&filename=${encodeURIComponent(file)}&_=${Date.now()}`);
            Object.assign(img.style, { width: "100%", height: "100%", objectFit: "cover", display: "block" });
            item.appendChild(img);

            // File name label
            const nameSpan = document.createElement("div");
            nameSpan.textContent = file;
            Object.assign(nameSpan.style, {
                position: "absolute", bottom: "0", left: "0",
                right: isVideo ? "0" : "22px",
                backgroundColor: "rgba(0,0,0,0.6)", color: "white",
                fontSize: "10px", textAlign: "center", padding: "2px",
                whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
            });
            item.appendChild(nameSpan);

            // Delete button
            const delBtn = document.createElement("button");
            delBtn.textContent = "✖";
            Object.assign(delBtn.style, {
                position: "absolute", top: "2px", right: "2px",
                backgroundColor: "rgba(0,0,0,0.6)", color: "white",
                border: "none", borderRadius: "50%", width: "20px",
                height: "20px", cursor: "pointer",
            });
            delBtn.onclick = (e) => {
                e.stopPropagation();
                item.remove();
                if (!isVideo) {
                    hiddenFiles.delete(file);
                    updateExcludeWidget();
                }
            };
            item.appendChild(delBtn);

            // Exclude button (image only)
            if (!isVideo) {
                const eyeBtn = document.createElement("button");
                eyeBtn.setAttribute("data-action", "exclude");
                eyeBtn.textContent = isHidden ? "🙈" : "👁️";
                eyeBtn.title = isHidden ? "Include" : "Exclude";
                Object.assign(eyeBtn.style, {
                    position: "absolute", bottom: "2px", right: "2px",
                    backgroundColor: "rgba(0,0,0,0.5)", color: "white",
                    border: "none", borderRadius: "50%", width: "18px",
                    height: "18px", fontSize: "12px", cursor: "pointer",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    padding: "0", lineHeight: "1",
                });
                eyeBtn.onclick = (e) => {
                    e.stopPropagation();
                    if (hiddenFiles.has(file)) hiddenFiles.delete(file);
                    else hiddenFiles.add(file);
                    const newHidden = hiddenFiles.has(file);
                    item.style.opacity = newHidden ? "0.45" : "1";
                    eyeBtn.textContent = newHidden ? "🙈" : "👁️";
                    eyeBtn.title = newHidden ? "Include" : "Exclude";
                    updateExcludeWidget();
                };
                item.appendChild(eyeBtn);
            }

            // Click to zoom — supports switching
            item.addEventListener("click", (e) => {
                if (e.target === delBtn || delBtn.contains(e.target)) return;
                if (!isVideo && e.target.closest('[data-action="exclude"]')) return;
                const idx = Array.from(listDiv.querySelectorAll(".media-item")).indexOf(item);
                overlay.showImage(idx, files, routeKey, subdirWidget.value);
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
            handle: ".media-item",
            ghostClass: "sortable-ghost",
            direction: "horizontal",
        });
    }

    // --- Button handlers ---
    uploadBtn.onclick = () => {
        const input = document.createElement("input");
        input.type = "file";
        input.multiple = true;
        input.accept = isVideo ? "video/*" : "image/*";
        input.onchange = async () => {
            if (!input.files.length) return;
            const files = Array.from(input.files);
            const orig = uploadBtn.textContent;
            uploadBtn.textContent = "Uploading...";
            uploadBtn.disabled = true;
            try {
                await uploadFiles(files, subdirWidget.value, (idx, prog) => {
                    uploadBtn.textContent = `Uploading ${idx + 1}/${files.length} ${Math.round(prog * 100)}%`;
                });
                await updateList();
                updateExcludeWidget();
                console.log("[CF_BatchMedia] Upload complete");
            } catch (err) {
                console.error("[CF_BatchMedia] Upload failed:", err.message);
            } finally {
                uploadBtn.textContent = orig;
                uploadBtn.disabled = false;
            }
        };
        input.click();
    };

    refreshBtn.onclick = async () => { await updateList(); console.log("[CF_BatchMedia] Refreshed"); };

    applyBtn.onclick = async () => {
        const items = listDiv.querySelectorAll(".media-item");
        const ordered = Array.from(items).map(i => i.getAttribute("data-filename"));
        try {
            await applyOrdering(routeKey, subdirWidget.value, ordered);
            if (!isVideo) hiddenFiles.clear();
            await updateList();
            if (!isVideo) updateExcludeWidget();
            console.log("[CF_BatchMedia] Ordering applied");
        } catch (err) {
            console.error("[CF_BatchMedia] Apply failed:", err.message);
        }
    };

    // Auto-refresh event
    api.addEventListener("cf_batch_media_refresh", (event) => {
        if (event.detail.subdir === subdirWidget.value) updateList();
    });

    const origCb = subdirWidget.callback;
    subdirWidget.callback = function (v) { origCb?.(v); updateList(); };
    updateList();
}

app.registerExtension({
    name: "CF_BatchMedia_UI",
    async nodeCreated(node) {
        if (node.comfyClass === TARGET_IMAGE_LOADER) {
            setTimeout(() => addUI(node, "image_input", false), 100);
        } else if (node.comfyClass === TARGET_IMAGE_MANAGER) {
            setTimeout(() => addUI(node, "image_output", false), 100);
        } else if (node.comfyClass === TARGET_VIDEO_LOADER) {
            setTimeout(() => addUI(node, "video_input", true), 100);
        } else if (node.comfyClass === TARGET_VIDEO_MANAGER) {
            setTimeout(() => addUI(node, "video_output", true), 100);
        }
    },
});

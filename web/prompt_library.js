import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

console.log("[CF_PromptLibrary] JS 脚本已加载");

const TARGET_CLASS = "CF_PromptLibrary";
const ROUTE_PREFIX = "/cf_toolkit/prompt_library/category_data";

function createMultiselectContainer(categoryId, items, currentSelections, onChanged) {
    const container = document.createElement("div");
    container.className = "cf-prompt-multiselect";
    container.style.display = "flex";
    container.style.flexWrap = "wrap";
    container.style.gap = "6px";
    container.style.margin = "4px 0";
    container.style.padding = "2px";
    container.style.border = "1px solid #3a3a3a";
    container.style.borderRadius = "4px";
    container.style.backgroundColor = "#2d2d2d";
    container.style.minHeight = "32px";

    items.forEach((item, idx) => {
        const label = document.createElement("label");
        label.style.display = "inline-flex";
        label.style.alignItems = "center";
        label.style.gap = "4px";
        label.style.margin = "2px 4px";
        label.style.cursor = "pointer";
        label.style.fontSize = "12px";
        label.style.color = "#ccc";

        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.value = idx;
        cb.checked = currentSelections.includes(idx);
        cb.style.margin = "0";
        cb.style.cursor = "pointer";

        const span = document.createElement("span");
        span.textContent = `${item.zh} (${item.en})`;

        label.appendChild(cb);
        label.appendChild(span);
        container.appendChild(label);

        cb.addEventListener("change", () => {
            const newSelections = Array.from(container.querySelectorAll("input:checked"))
                .map(cb => parseInt(cb.value));
            onChanged(newSelections);
        });
    });
    return container;
}

async function fetchCategoryData(catId) {
    const resp = await fetch(api.apiURL(`${ROUTE_PREFIX}?cat=${encodeURIComponent(catId)}`));
    if (!resp.ok) throw new Error(`Failed to load category data: ${catId}`);
    const data = await resp.json();
    return data;
}

function addMultiselectUI(node) {
    console.log("[CF_PromptLibrary] addMultiselectUI called for node", node.id);
    if (node._multiselectAdded) return;
    node._multiselectAdded = true;

    const multiselectWidgets = node.widgets.filter(w => w.name.endsWith("_multiselect"));
    console.log("[CF_PromptLibrary] Found multiselect widgets:", multiselectWidgets.length);
    if (multiselectWidgets.length === 0) return;

    for (const widget of multiselectWidgets) {
        const catId = widget.name.replace("_multiselect", "");
        console.log(`[CF_PromptLibrary] Loading category: ${catId}`);
        fetchCategoryData(catId).then(data => {
            if (!data.items) return;
            let currentSelections = [];
            try {
                currentSelections = JSON.parse(widget.value);
            } catch(e) {}
            const container = createMultiselectContainer(catId, data.items, currentSelections, (newSelections) => {
                widget.value = JSON.stringify(newSelections);
                // 触发节点重新执行：通过修改一个临时 widget 的值
                let trigger = node.widgets.find(w => w.name === "__trigger__");
                if (!trigger) {
                    // 添加一个隐藏的字符串 widget 用于触发更新
                    node.addWidget("STRING", "__trigger__", "0", () => {}, { serialize: false });
                    trigger = node.widgets.find(w => w.name === "__trigger__");
                }
                if (trigger) {
                    trigger.value = String(Date.now());
                    if (trigger.callback) trigger.callback(trigger.value);
                }
            });
            // 找到隐藏 widget 对应的 DOM 元素位置，在其后插入容器
            if (widget.element) {
                const widgetRow = widget.element.closest(".comfy-widget");
                if (widgetRow) {
                    widgetRow.insertAdjacentElement("afterend", container);
                } else {
                    widget.element.insertAdjacentElement("afterend", container);
                }
            } else {
                // 降级：直接添加到节点主体末尾
                const nodeEl = document.querySelector(`.comfy-node[data-id="${node.id}"] .comfy-node-body`);
                if (nodeEl) nodeEl.appendChild(container);
            }
        }).catch(err => console.error(`[CF_PromptLibrary] 加载 ${catId} 失败:`, err));
    }
}

app.registerExtension({
    name: "CF.PromptLibraryMultiselect",
    async nodeCreated(node) {
        if (node.comfyClass === TARGET_CLASS) {
            console.log("[CF_PromptLibrary] Node created, scheduling UI addition");
            setTimeout(() => addMultiselectUI(node), 200);
        }
    },
});
import os
import re
import torch
import numpy as np
from PIL import Image
import folder_paths
import server
from aiohttp import web
import mimetypes

# ---------- 工具函数 ----------
def get_output_subdir(subdir=""):
    base = folder_paths.get_output_directory()
    if not subdir:
        subdir = "batch_outputs"
    target = os.path.normpath(os.path.join(base, subdir))
    if not target.startswith(os.path.normpath(base)):
        raise ValueError(f"非法子目录: {subdir}")
    os.makedirs(target, exist_ok=True)
    return target

def list_output_images(subdir):
    target = get_output_subdir(subdir)
    pattern = re.compile(r'^(\d+)\.(png|jpg|jpeg)$', re.IGNORECASE)
    files = []
    for f in os.listdir(target):
        m = pattern.match(f)
        if m:
            files.append((int(m.group(1)), f))
    files.sort(key=lambda x: x[0])
    return [f for _, f in files]

# ---------- 管理路由 ----------
async def output_list(request):
    subdir = request.query.get("subdir", "")
    try:
        files = list_output_images(subdir)
        return web.json_response({"files": files})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def output_preview(request):
    subdir = request.query.get("subdir", "")
    filename = request.query.get("filename", "")
    if not filename:
        return web.json_response({"error": "no filename"}, status=400)
    try:
        target = get_output_subdir(subdir)
        safe_path = os.path.join(target, os.path.basename(filename))
        if not os.path.exists(safe_path):
            return web.json_response({"error": "file not found"}, status=404)
        return web.FileResponse(safe_path, headers={
            "Content-Type": mimetypes.guess_type(safe_path)[0] or "image/png",
            "Cache-Control": "no-store, no-cache, must-revalidate"
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def output_apply(request):
    data = await request.json()
    subdir = data.get("subdir", "")
    ordered_filenames = data.get("ordered_filenames", [])
    try:
        target = get_output_subdir(subdir)
        existing = set(list_output_images(subdir))
        to_delete = existing - set(ordered_filenames)
        for f in to_delete:
            os.remove(os.path.join(target, f))
        temp_map = []
        for i, old_name in enumerate(ordered_filenames):
            ext = old_name.split('.')[-1]
            new_name = f"{i:03d}.{ext}"
            old_path = os.path.join(target, old_name)
            temp_path = os.path.join(target, f"_temp_{i}_{old_name}")
            os.rename(old_path, temp_path)
            temp_map.append((temp_path, new_name))
        for temp_path, new_name in temp_map:
            os.rename(temp_path, os.path.join(target, new_name))
        files = list_output_images(subdir)
        return web.json_response({"files": files})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

try:
    server.PromptServer.instance.routes.get("/batchimage/output/list")(output_list)
    server.PromptServer.instance.routes.get("/batchimage/output/preview")(output_preview)
    server.PromptServer.instance.routes.post("/batchimage/output/apply")(output_apply)
except Exception as e:
    print(f"[CF_BatchImageManager] 路由注册失败: {e}")

class CF_BatchImageManager:
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "图像批次": ("IMAGE",),
                "子目录": ("STRING", {"default": "batch_outputs", "label": "子目录"}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "IMAGE", "INT")
    RETURN_NAMES = ("文件列表", "文件夹路径", "图像批次", "批次数量")
    FUNCTION = "save_images"
    CATEGORY = "CF工具包"

    def save_images(self, 图像批次, 子目录="batch_outputs"):
        target = get_output_subdir(子目录)

        # --- 保存输入的图像批次 ---
        pattern = re.compile(r'^(\d+)\.(png|jpg|jpeg)$', re.IGNORECASE)
        existing_max = -1
        for f in os.listdir(target):
            m = pattern.match(f)
            if m:
                existing_max = max(existing_max, int(m.group(1)))
        next_num = existing_max + 1

        batch_tensor = 图像批次
        for i in range(batch_tensor.shape[0]):
            arr = (batch_tensor[i].cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
            img = Image.fromarray(arr, "RGB")
            filename = f"{next_num + i:03d}.png"
            filepath = os.path.join(target, filename)
            img.save(filepath)

        # --- 读取当前子目录下的所有图片，组成输出批次 ---
        files = list_output_images(子目录)
        if not files:
            batch = torch.zeros(0, 1, 1, 3)  # 空张量
            file_list_str = "无图片，请先上传"
            folder_path = f"{target}/{{:03d}}.png".replace("\\", "/")
            batch_count = 0
        else:
            images = []
            for f in files:
                file_path = os.path.join(target, f)
                img = Image.open(file_path).convert("RGB")
                arr = np.array(img).astype(np.float32) / 255.0
                images.append(torch.from_numpy(arr).unsqueeze(0))
            batch = torch.cat(images, dim=0)
            file_list_str = "\n".join(files)
            folder_path = f"{target}/{{:03d}}.png".replace("\\", "/")
            batch_count = len(files)

        # 发送刷新事件
        try:
            server.PromptServer.instance.send_sync(
                "batchimage_manager_refresh",
                {"subdir": 子目录}
            )
        except Exception as e:
            print(f"[CF_BatchImageManager] 发送刷新事件失败: {e}")

        return (file_list_str, folder_path, batch, batch_count)

NODE_CLASS_MAPPINGS = {"CF_BatchImageManager": CF_BatchImageManager}
NODE_DISPLAY_NAME_MAPPINGS = {"CF_BatchImageManager": "CF 批量图像管理器"}
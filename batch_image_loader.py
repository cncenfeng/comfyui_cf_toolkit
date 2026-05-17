import os
import re
import torch
import numpy as np
from PIL import Image
from torch.nn.functional import interpolate
import folder_paths
import server
from aiohttp import web
import mimetypes

def get_image_dir(subdir=""):
    input_dir = folder_paths.get_input_directory()
    if not subdir:
        subdir = "batch_uploads"
    target_dir = os.path.join(input_dir, subdir)
    os.makedirs(target_dir, exist_ok=True)
    return target_dir

def list_images(target_dir):
    pattern = re.compile(r'^(\d+)\.(png|jpg|jpeg)$', re.IGNORECASE)
    files = []
    for f in os.listdir(target_dir):
        m = pattern.match(f)
        if m:
            files.append((int(m.group(1)), f))
    files.sort(key=lambda x: x[0])
    return [f for _, f in files]

def load_image(file_path):
    img = Image.open(file_path).convert("RGB")
    arr = np.array(img).astype(np.float32) / 255.0
    return torch.from_numpy(arr).unsqueeze(0)

# ---------- 缩放/裁剪辅助函数 ----------
def apply_resize_single(image_tensor, target_width, target_height):
    """对单张图像 [1, H, W, C] 进行缩放/裁剪，返回 [1, H', W', C]"""
    if target_width == 0 and target_height == 0:
        return image_tensor

    _, H, W, C = image_tensor.shape
    if target_width > 0 and target_height == 0:
        scale = target_width / W
        new_w = target_width
        new_h = int(round(H * scale))
    elif target_width == 0 and target_height > 0:
        scale = target_height / H
        new_h = target_height
        new_w = int(round(W * scale))
    else:  # 两者均大于0
        scale = max(target_width / W, target_height / H)
        new_w = int(round(W * scale))
        new_h = int(round(H * scale))

    img_nchw = image_tensor.permute(0, 3, 1, 2)
    scaled = interpolate(img_nchw, size=(new_h, new_w), mode='bilinear', align_corners=False)

    if target_width > 0 and target_height > 0:
        start_h = (new_h - target_height) // 2
        start_w = (new_w - target_width) // 2
        end_h = start_h + target_height
        end_w = start_w + target_width
        scaled = scaled[:, :, start_h:end_h, start_w:end_w]

    result = scaled.permute(0, 2, 3, 1)
    result = torch.clamp(result, 0.0, 1.0)
    return result

# ---------- HTTP 路由 ----------
async def get_preview(request):
    subdir = request.query.get("subdir", "")
    filename = request.query.get("filename", "")
    if not filename:
        return web.json_response({"error": "no filename"}, status=400)
    target_dir = get_image_dir(subdir)
    safe_path = os.path.join(target_dir, os.path.basename(filename))
    if not os.path.exists(safe_path):
        return web.json_response({"error": "file not found"}, status=404)
    return web.FileResponse(safe_path, headers={
        "Content-Type": mimetypes.guess_type(safe_path)[0] or "image/png",
        "Cache-Control": "no-store, no-cache, must-revalidate"
    })

async def get_next_number(request):
    subdir = request.query.get("subdir", "")
    target_dir = get_image_dir(subdir)
    used = set()
    for f in os.listdir(target_dir):
        m = re.match(r'^(\d+)', f)
        if m:
            used.add(int(m.group(1)))
    next_num = 0
    while next_num in used:
        next_num += 1
    return web.json_response({"next_num": next_num})

async def get_file_list(request):
    subdir = request.query.get("subdir", "")
    target_dir = get_image_dir(subdir)
    files = list_images(target_dir)
    return web.json_response({"files": files})

async def apply_changes(request):
    data = await request.json()
    subdir = data.get("subdir", "")
    ordered_filenames = data.get("ordered_filenames", [])
    target_dir = get_image_dir(subdir)
    existing = set(list_images(target_dir))
    to_delete = existing - set(ordered_filenames)
    for f in to_delete:
        os.remove(os.path.join(target_dir, f))
    temp_map = []
    for i, old_name in enumerate(ordered_filenames):
        ext = old_name.split('.')[-1]
        new_name = f"{i:03d}.{ext}"
        old_path = os.path.join(target_dir, old_name)
        temp_path = os.path.join(target_dir, f"_temp_{i}_{old_name}")
        os.rename(old_path, temp_path)
        temp_map.append((temp_path, new_name))
    for temp_path, new_name in temp_map:
        os.rename(temp_path, os.path.join(target_dir, new_name))
    new_files = list_images(target_dir)
    return web.json_response({"files": new_files})

try:
    server.PromptServer.instance.routes.get("/batchimage/preview")(get_preview)
    server.PromptServer.instance.routes.get("/batchimage/next_number")(get_next_number)
    server.PromptServer.instance.routes.get("/batchimage/list")(get_file_list)
    server.PromptServer.instance.routes.post("/batchimage/apply")(apply_changes)
except Exception as e:
    print(f"[CF_BatchImageLoader] 路由注册失败: {e}")

class CF_BatchImageLoader:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "子目录": ("STRING", {"default": "batch_uploads", "label": "子目录"}),
                "宽度": ("INT", {"default": 0, "min": 0, "max": 8192, "step": 1, "label": "宽度 (0=不缩放)"}),
                "高度": ("INT", {"default": 0, "min": 0, "max": 8192, "step": 1, "label": "高度 (0=不缩放)"}),
                # 隐藏参数：前端自动维护，逗号分隔的被排除文件名列表
                "排除文件": ("STRING", {"default": "", "visible": False}),
                "刷新触发器": ("INT", {"default": 0, "min": 0, "max": 0xffffffff, "step": 1, "visible": False}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "IMAGE", "INT")
    RETURN_NAMES = ("文件列表", "文件夹路径", "图像批次", "批次数量")
    FUNCTION = "run"
    CATEGORY = "CF工具包"

    def run(self, 子目录="batch_uploads", 宽度=0, 高度=0, 排除文件="", 刷新触发器=0):
        target_dir = get_image_dir(子目录)
        files = list_images(target_dir)

        # 过滤排除文件
        exclude_set = set(filter(None, (f.strip() for f in 排除文件.split(","))))
        filtered_files = [f for f in files if f not in exclude_set]

        if not filtered_files:
            file_list_str = "无图片，请先上传"
            folder_path = f"{target_dir}/{{:03d}}.png".replace("\\", "/")
            batch = torch.zeros(0, 1, 1, 3)
            batch_count = 0
        else:
            file_list_str = "\n".join(filtered_files)
            folder_path = f"{target_dir}/{{:03d}}.png".replace("\\", "/")

            images = []
            for f in filtered_files:
                file_path = os.path.join(target_dir, f)
                img = Image.open(file_path).convert("RGB")
                arr = np.array(img).astype(np.float32) / 255.0
                tensor = torch.from_numpy(arr).unsqueeze(0)
                tensor = apply_resize_single(tensor, 宽度, 高度)
                images.append(tensor)

            if 宽度 == 0 and 高度 == 0:
                shapes = [img.shape for img in images]
                if len(set(shapes)) != 1:
                    raise ValueError(
                        f"未设置缩放参数时，所有图片尺寸必须相同。当前包含 {len(set(shapes))} 种不同尺寸：\n"
                        + "\n".join(f"{f}: {s}" for f, s in zip(filtered_files, shapes))
                    )

            batch = torch.cat(images, dim=0)
            batch_count = len(filtered_files)

        return (file_list_str, folder_path, batch, batch_count)

NODE_CLASS_MAPPINGS = {"CF_BatchImageLoader": CF_BatchImageLoader}
NODE_DISPLAY_NAME_MAPPINGS = {"CF_BatchImageLoader": "CF 批量图像加载器"}
"""
CF_BatchImageLoader + CF_BatchImageManager — two nodes, shared logic.
Uses media_utils.py for directory management, file listing, and HTTP routes.
"""
import os
import torch
import numpy as np
from PIL import Image
from torch.nn.functional import interpolate
import server

from .cf_help_loader import get_help_en
from .media_utils import (
    get_input_dir, get_output_dir,
    list_media_files, get_next_number, clear_directory,
    register_media_routes,
)

IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg"]

register_media_routes("image_input",  lambda s: get_input_dir(s or "batch_uploads"))
register_media_routes("image_output", lambda s: get_output_dir(s or "batch_outputs"))


def apply_resize_single(image_tensor, target_width, target_height):
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
    else:
        scale = max(target_width / W, target_height / H)
        new_w = int(round(W * scale))
        new_h = int(round(H * scale))
    img_nchw = image_tensor.permute(0, 3, 1, 2)
    scaled = interpolate(img_nchw, size=(new_h, new_w), mode="bilinear", align_corners=False)
    if target_width > 0 and target_height > 0:
        start_h = (new_h - target_height) // 2
        start_w = (new_w - target_width) // 2
        scaled = scaled[:, :, start_h:start_h + target_height, start_w:start_w + target_width]
    result = scaled.permute(0, 2, 3, 1)
    result = torch.clamp(result, 0.0, 1.0)
    return result


def load_and_resize(file_path, width, height):
    img = Image.open(file_path).convert("RGB")
    arr = np.array(img).astype(np.float32) / 255.0
    tensor = torch.from_numpy(arr).unsqueeze(0)
    return apply_resize_single(tensor, width, height)


def _load_batch(target_dir, files, exclude_set, width, height):
    filtered = [f for f in files if f not in exclude_set]
    if not filtered:
        return torch.zeros(0, 1, 1, 3), 0
    images = [load_and_resize(os.path.join(target_dir, f), width, height) for f in filtered]
    return torch.cat(images, dim=0), len(filtered)


class CF_BatchImageLoader:
    DESCRIPTION = get_help_en("CF_BatchImageLoader")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "subdirectory":  ("STRING",  {"default": "batch_uploads", "label": "子目录"}),
                "width":         ("INT",     {"default": 0, "min": 0, "max": 8192, "step": 1, "label": "输出宽度 (0=原样)"}),
                "height":        ("INT",     {"default": 0, "min": 0, "max": 8192, "step": 1, "label": "输出高度 (0=原样)"}),
                "exclude_files": ("STRING",  {"default": "", "visible": False}),
            }
        }

    RETURN_TYPES = ("IMAGE", "INT")
    RETURN_NAMES = ("image_batch", "batch_count")
    FUNCTION = "run"
    CATEGORY = "CF工具包"

    def run(self, subdirectory="batch_uploads", width=0, height=0, exclude_files=""):
        target_dir = get_input_dir(subdirectory)
        files = list_media_files(target_dir, IMAGE_EXTENSIONS)
        exclude_set = set(filter(None, (f.strip() for f in exclude_files.split(","))))
        return _load_batch(target_dir, files, exclude_set, width, height)


class CF_BatchImageManager:
    OUTPUT_NODE = True
    DESCRIPTION = get_help_en("CF_BatchImageManager")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_batch":   ("IMAGE",),
                "subdirectory":  ("STRING",  {"default": "batch_outputs", "label": "子目录"}),
                "overwrite":     ("BOOLEAN", {"default": True, "label": "覆盖模式 (关闭=追加)"}),
                "width":         ("INT",     {"default": 0, "min": 0, "max": 8192, "step": 1, "label": "输出宽度 (0=原样)"}),
                "height":        ("INT",     {"default": 0, "min": 0, "max": 8192, "step": 1, "label": "输出高度 (0=原样)"}),
                "exclude_files": ("STRING",  {"default": "", "visible": False}),
            }
        }

    RETURN_TYPES = ("IMAGE", "INT")
    RETURN_NAMES = ("image_batch", "batch_count")
    FUNCTION = "save_and_load"
    CATEGORY = "CF工具包"

    def save_and_load(self, image_batch, subdirectory="batch_outputs", overwrite=True,
                      width=0, height=0, exclude_files=""):
        target_dir = get_output_dir(subdirectory)
        if overwrite:
            clear_directory(target_dir)
        next_num = get_next_number(target_dir)
        for i in range(image_batch.shape[0]):
            arr = (image_batch[i].cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
            img = Image.fromarray(arr, "RGB")
            filename = f"{next_num + i:03d}.png"
            img.save(os.path.join(target_dir, filename))

        files = list_media_files(target_dir, IMAGE_EXTENSIONS)
        exclude_set = set(filter(None, (f.strip() for f in exclude_files.split(","))))
        result = _load_batch(target_dir, files, exclude_set, width, height)

        try:
            server.PromptServer.instance.send_sync(
                "cf_batch_media_refresh", {"subdir": subdirectory}
            )
        except Exception as e:
            print(f"[CF_BatchImageManager] refresh event failed: {e}")

        return result


NODE_CLASS_MAPPINGS = {
    "CF_BatchImageLoader":  CF_BatchImageLoader,
    "CF_BatchImageManager": CF_BatchImageManager,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "CF_BatchImageLoader":  "CF 批量图像加载器",
    "CF_BatchImageManager": "CF 批量图像管理器",
}

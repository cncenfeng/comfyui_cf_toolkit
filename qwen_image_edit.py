import torch
import math
import re
import comfy.utils
import node_helpers

# 短版系统提示词（单行，无换行）
DEFAULT_SYSTEM_INSTRUCTION = "Analyze the input image's artistic style, lighting, color palette, texture quality, overall mood, and the main character's facial features, body proportions, and unique identity traits. Then explain how the user's instruction alters the image. Finally generate a new image that strictly preserves the analyzed style, lighting, colors, and texture, keeps the character's facial identity, body proportions, and unique traits completely consistent, precisely applies the user's modifications, and maintains overall image coherence."

DEFAULT_ASSISTANT_PRIMING = "A bright and youthful campus romance film still, soft pastel tones, clean and fresh atmosphere, light and airy feel, natural skin texture, realistic cinematic lighting, shot on a Sony A7III."

class CF_QwenImageEditEnhanced:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "clip": ("CLIP",),
                "USER_PROMPT": ("STRING", {
                    "multiline": True,
                    "dynamicPrompts": True,
                    "placeholder": "每行一个场景描述。使用 [pic:N] 引用图片（从1开始）。第一个引用的图片会作为主图输出。"
                }),
                "场景索引": ("INT", {"default": 1, "min": 1, "max": 1000, "step": 1, "label": "场景索引（第几行）"}),
                "SYSTEM_INSTRUCTION": ("STRING", {
                    "multiline": True,
                    "default": DEFAULT_SYSTEM_INSTRUCTION,
                }),
                "ASSISTANT_PRIMING": ("STRING", {
                    "multiline": True,
                    "default": DEFAULT_ASSISTANT_PRIMING,
                }),
            },
            "optional": {
                "vae": ("VAE",),
                "image": ("IMAGE",),   # 批次输入，不限数量
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("CONDITIONING", "IMAGE", "INT")
    RETURN_NAMES = ("conditioning", "first_image", "total_lines")
    FUNCTION = "encode"
    CATEGORY = "CF工具包"
    DESCRIPTION = "CF Qwen Image Edit with dynamic image reference via [pic:N] tags. Supports repeated references and arbitrary batch size."

    def encode(self, clip, USER_PROMPT, 场景索引, SYSTEM_INSTRUCTION, ASSISTANT_PRIMING, unique_id=None, vae=None, image=None):
        # ---- 1. 解析场景 ----
        lines = [line.strip() for line in USER_PROMPT.split("\n") if line.strip()]
        if not lines:
            lines = [USER_PROMPT.strip() or "Default scene"]
        total_lines = len(lines)
        idx = max(0, min(场景索引 - 1, total_lines - 1))
        selected_prompt = lines[idx]

        # ---- 2. 提取所有 [pic:N] 并按顺序记录是否有效 ----
        pic_matches = re.findall(r'\[pic:(\d+)\]', selected_prompt)
        valid_flags = []          # 每个匹配是否有效 (bool)
        ref_indices = []          # 每个匹配对应的图片索引 (1-based, 有效时)
        for m in pic_matches:
            n = int(m)
            if image is not None and 1 <= n <= image.shape[0]:
                valid_flags.append(True)
                ref_indices.append(n)
            else:
                valid_flags.append(False)
                ref_indices.append(-1)  # 无效占位

        # ---- 3. 构建 images_vl 和 ref_latents（支持缓存重复引用） ----
        images_vl = []
        ref_latents_list = []
        total_vision_tokens = 0
        token_report_str = ""
        first_image = None

        # 缓存已经处理过的图片（visual 和 vae latent）
        cache_vl = {}   # key: 1-based index, value: (s_vl_moved, img_tokens)
        cache_latent = {}  # key: 1-based index, value: latent

        if image is not None and image.numel() > 0 and image.shape[0] > 0:
            for n in ref_indices:
                if n == -1:
                    continue
                # 缓存命中
                if n not in cache_vl:
                    single_img = image[n - 1].unsqueeze(0)
                    samples = single_img.movedim(-1, 1)

                    # 视觉编码缩放
                    total_vl = int(384 * 384)
                    scale_by_vl = math.sqrt(total_vl / (samples.shape[3] * samples.shape[2]))
                    width_vl = round(samples.shape[3] * scale_by_vl)
                    height_vl = round(samples.shape[2] * scale_by_vl)
                    tokens_w = width_vl // 14
                    tokens_h = height_vl // 14
                    img_tokens = tokens_w * tokens_h
                    total_vision_tokens += img_tokens

                    s_vl = comfy.utils.common_upscale(samples, width_vl, height_vl, "area", "disabled")
                    s_vl_moved = s_vl.movedim(1, -1)
                    cache_vl[n] = (s_vl_moved, img_tokens)

                    # VAE 参考 latent（可选）
                    if vae is not None:
                        total_vae = int(1024 * 1024)
                        scale_by_vae = math.sqrt(total_vae / (samples.shape[3] * samples.shape[2]))
                        width_vae = round(samples.shape[3] * scale_by_vae / 8.0) * 8
                        height_vae = round(samples.shape[2] * scale_by_vae / 8.0) * 8
                        s_vae = comfy.utils.common_upscale(samples, width_vae, height_vae, "area", "disabled")
                        latent = vae.encode(s_vae.movedim(1, -1)[:, :, :, :3])
                        cache_latent[n] = latent

                    if f"[Orig{n}:" not in token_report_str:
                        token_report_str += f"[Orig{n}:{img_tokens}] "
                else:
                    pass  # 缓存命中，不重复统计 unique token

                # 从缓存取出视觉数据并添加到列表（重复引用也添加）
                s_vl_moved, _ = cache_vl[n]
                images_vl.append(s_vl_moved)
                if vae is not None and n in cache_latent:
                    ref_latents_list.append(cache_latent[n])

                if first_image is None:
                    single_img = image[n - 1].unsqueeze(0)
                    first_image = single_img.clone()
        else:
            pass

        if first_image is None:
            first_image = torch.zeros(1, 1, 1, 3)

        # ---- 4. 将 [pic:N] 替换为视觉占位符（有效）或保留原标记（无效） ----
        def replace_pic_with_flags(text, flags):
            """按顺序替换 [pic:N]，有效 -> <vision_start><image_pad><vision_end>，无效 -> 保留原文"""
            counter = 0
            def repl(match):
                nonlocal counter
                if counter < len(flags):
                    is_valid = flags[counter]
                    counter += 1
                    if is_valid:
                        return "<|vision_start|><|image_pad|><|vision_end|>"
                    else:
                        return match.group(0)  # 保留 [pic:N] 原文
                return match.group(0)
            return re.sub(r'\[pic:\d+\]', repl, text)

        clean_prompt = replace_pic_with_flags(selected_prompt, valid_flags)

        if not all(valid_flags):
            invalid_indices = [m for m, flag in zip(pic_matches, valid_flags) if not flag]
            print(f"[QwenEdit] Warning: Invalid [pic:N] indices detected and kept in text: {invalid_indices}")

        # ---- 5. 对话模板 ----
        llama_template_structure = (
            f"<|im_start|>system\n{SYSTEM_INSTRUCTION}<|im_end|>\n"
            f"<|im_start|>user\n{{}}<|im_end|>\n"
            f"<|im_start|>assistant\n{ASSISTANT_PRIMING}<|im_end|>"
        )

        # ---- 6. 编码 ----
        combined_content = clean_prompt
        final_prompt_string = llama_template_structure.format(combined_content)

        tokens = clip.tokenize(combined_content, images=images_vl, llama_template=llama_template_structure)

        text_token_count = 0
        if "l" in tokens:
            text_token_count = len(tokens["l"][0])
        elif "g" in tokens:
            text_token_count = len(tokens["g"][0])
        else:
            first_key = next(iter(tokens), None)
            if first_key and isinstance(tokens[first_key], list):
                text_token_count = len(tokens[first_key][0])

        grand_total = total_vision_tokens + text_token_count
        conditioning = clip.encode_from_tokens_scheduled(tokens)

        if len(ref_latents_list) > 0:
            conditioning = node_helpers.conditioning_set_values(conditioning, {"reference_latents": ref_latents_list}, append=True)

        # ---- 7. 控制台输出 ----
        if grand_total > 0:
            debug_msg = f"[QwenEdit] Total: {grand_total} (Vis: {total_vision_tokens} + Txt: {text_token_count}) | Unique refs: {token_report_str}"
        else:
            debug_msg = "[QwenEdit] No valid inputs detected."
        print(debug_msg)
        print(f"[QwenEdit] Final Prompt:\n{final_prompt_string}")

        return (conditioning, first_image, total_lines)

NODE_CLASS_MAPPINGS = {"CF_QwenImageEditEnhanced": CF_QwenImageEditEnhanced}
NODE_DISPLAY_NAME_MAPPINGS = {"CF_QwenImageEditEnhanced": "CF Qwen Image Edit (Batch Image)"}
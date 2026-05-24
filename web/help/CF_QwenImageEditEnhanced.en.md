Intelligent image editing node powered by Qwen2.5-VL.

**Core feature:** use [pic:N] tags in USER_PROMPT to dynamically reference images from the connected image batch.
The first referenced image becomes the main image output to `first_image`.

**Parameters:**
- clip: CLIP model (usually Qwen2.5-VL based)
- USER_PROMPT: one scene description per line. Use [pic:N] to reference image #N (1-based)
- scene_index: which line of USER_PROMPT to use (default: 1)
- SYSTEM_INSTRUCTION: system-level instruction for the vision model
- ASSISTANT_PRIMING: assistant priming text to guide output style
- vae: optional VAE for reference latent encoding
- image: batch of reference images (used by [pic:N] tags)

**Example:**
Image batch: [1: portrait], [2: outfit reference]
Prompt: Let [pic:1] wear the clothes from [pic:2], change background to white.
Result: pic1 is the main output, dressed in pic2's outfit.
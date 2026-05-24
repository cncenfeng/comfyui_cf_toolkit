Receives an image batch, saves to output subdirectory, then re-reads and outputs the full directory as a tensor batch.

- image_batch: input images to save (required)
- subdirectory: folder under ComfyUI/output/
- overwrite: ON = clear directory before saving, OFF = append (continue numbering)
- width/height: resize output images. 0 = keep original size

Useful for iterative workflows where each generation run accumulates images in the output folder.
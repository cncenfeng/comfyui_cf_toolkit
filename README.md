CF 工具包 (comfyui_cf_toolkit)
为 ComfyUI 设计的自定义节点包，提供图像管理、智能编辑和逻辑控制功能，深度集成 Qwen2.5-VL 视觉语言模型。

1. 安装
环境要求: 最新版 ComfyUI，支持 Windows/Linux/macOS。

进入 ComfyUI 的 custom_nodes 目录：

bash
cd ComfyUI/custom_nodes
克隆仓库：

bash
git clone https://github.com/cncenfeng/comfyui_cf_toolkit
安装依赖（若节点未自带 requirements.txt，将在首次运行时自动安装）：
cncenfeng
bash
cd comfyui_cf_toolkit
pip install -r requirements.txt
重启 ComfyUI。

2. 节点说明
所有节点位于 CF工具包 类别下。

节点名称	功能描述
CF 批量图像加载器	从指定子文件夹加载图像批次，提供固定高度、水平滚动的预览面板，支持上传、拖拽排序、重命名、删除。可设置宽高缩放并统一输出尺寸。
CF 批量图像管理器	接收图像批次，自动保存到输出目录，并重新读取文件夹内所有图像输出完整批次。预览面板与加载器一致，支持删除和排序。
CF Qwen Image Edit (Batch Image)	基于 Qwen2.5-VL 的智能图像编辑节点。使用 [pic:N] 标记动态选择主图和参考图，支持换装、多角色互动等复杂编辑。详细用法见下方高级功能。
CF 通用运算器	集成算术、逻辑、比较、聚合共 20 余种运算模式。输入输出采用万能类型 *，自动返回整数、浮点数或布尔值。
3. [pic:N] 标记语法详解
在 USER_PROMPT 中插入 [pic:N] 标记，节点将按提及顺序重新排列图片，第一个被提及的 [pic:N] 自动成为主图，输出到 first_image 端口。

示例：

图像批次: [Pic1: 人物], [Pic2: 服装A]

提示词: 让 [pic:1] 的人物穿上 [pic:2] 的衣服，背景改为纯白色。

效果: Pic1 为主图，参考 Pic2 服装生成最终图像。

支持多角色控制，例如：让 [pic:1] 穿上 [pic:6] 的衬衫，用 [pic:2] 的裤子，在 [pic:5] 的场景中。
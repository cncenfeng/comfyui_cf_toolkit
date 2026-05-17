class CF_UniversalCalculator:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "A": ("*", {"default": 0}),   # 万能输入，默认整数 0
                "B": ("*", {"default": 0}),
                "运算模式": ([
                    "Add (➕)", "Sub (➖)", "Mul (✖)", "Div (➗)", "Mod (余)", "Pow (幂)",
                    "Eq (等于)", "Neq (不等于)", "Gt (大于)", "Gte (>=)", "Lt (小于)", "Lte (<=)",
                    "And (与)", "Nand (与非)", "Or (或)", "Nor (或非)",
                    "Xor (异或)", "Xnor (同或)", "Not (非-A)",
                    "Max (最大值)", "Min (最小值)"
                ], {"default": "Add (➕)"}),
            }
        }

    RETURN_TYPES = ("*", "STRING")
    RETURN_NAMES = ("结果", "表达式")
    FUNCTION = "calculate"
    CATEGORY = "CF工具包"

    def calculate(self, A, B, 运算模式):
        mode = 运算模式.split(" ")[0]   # 提取英文缩写

        # 将输入尝试转换为数字（如果是 str），否则保持原样
        def to_num(x):
            if isinstance(x, (int, float)):
                return x
            try:
                return float(x)
            except (ValueError, TypeError):
                return x   # 无法转换则保留，后续运算可能报错

        a = to_num(A)
        b = to_num(B)

        # ---- 算术 ----
        if mode == "Add":
            result = a + b
        elif mode == "Sub":
            result = a - b
        elif mode == "Mul":
            result = a * b
        elif mode == "Div":
            result = a / b if b != 0 else float("nan")
        elif mode == "Mod":
            result = a % b if b != 0 else float("nan")
        elif mode == "Pow":
            result = a ** b

        # ---- 比较（输出布尔值）----
        elif mode == "Eq":
            result = a == b
        elif mode == "Neq":
            result = a != b
        elif mode == "Gt":
            result = a > b
        elif mode == "Gte":
            result = a >= b
        elif mode == "Lt":
            result = a < b
        elif mode == "Lte":
            result = a <= b

        # ---- 逻辑/位（输出布尔值）----
        elif mode == "And":
            result = (a != 0) and (b != 0)
        elif mode == "Nand":
            result = not ((a != 0) and (b != 0))
        elif mode == "Or":
            result = (a != 0) or (b != 0)
        elif mode == "Nor":
            result = not ((a != 0) or (b != 0))
        elif mode == "Xor":
            result = (bool(a) != bool(b))
        elif mode == "Xnor":
            result = (bool(a) == bool(b))
        elif mode == "Not":
            result = a == 0   # 若 a 为 0 则 True，否则 False

        # ---- 聚合 ----
        elif mode == "Max":
            result = max(a, b)
        elif mode == "Min":
            result = min(a, b)

        else:
            result = None

        # 表达式字符串，直接显示原生结果
        if mode == "Not":
            expr = f"NOT {A} = {result}"
        else:
            expr = f"{A} {mode} {B} = {result}"

        return (result, expr)

NODE_CLASS_MAPPINGS = {"CF_UniversalCalculator": CF_UniversalCalculator}
NODE_DISPLAY_NAME_MAPPINGS = {"CF_UniversalCalculator": "CF 通用运算器"}
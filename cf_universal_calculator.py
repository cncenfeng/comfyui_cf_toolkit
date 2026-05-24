from .cf_help_loader import get_help_en

class CF_UniversalCalculator:
    DESCRIPTION = get_help_en("CF_UniversalCalculator")

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "A": ("*", {"default": 0}),
                "B": ("*", {"default": 0}),
                "operation": ([
                    "Add (➕)", "Sub (➖)", "Mul (✖)", "Div (➗)", "Mod (余)", "Pow (幂)",
                    "Eq (等于)", "Neq (不等于)", "Gt (大于)", "Gte (>=)", "Lt (小于)", "Lte (<=)",
                    "And (与)", "Nand (与非)", "Or (或)", "Nor (或非)",
                    "Xor (异或)", "Xnor (同或)", "Not (非-A)",
                    "Max (最大值)", "Min (最小值)"
                ], {"default": "Add (➕)"}),
            }
        }

    RETURN_TYPES = ("*", "STRING")
    RETURN_NAMES = ("result", "expression")
    FUNCTION = "calculate"
    CATEGORY = "CF工具包"

    def calculate(self, A, B, operation):
        mode = operation.split(" ")[0]

        def to_num(x):
            if isinstance(x, (int, float)):
                return x
            try:
                return float(x)
            except (ValueError, TypeError):
                return x

        a = to_num(A)
        b = to_num(B)

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
            result = a == 0
        elif mode == "Max":
            result = max(a, b)
        elif mode == "Min":
            result = min(a, b)
        else:
            result = None

        if mode == "Not":
            expr = f"NOT {A} = {result}"
        else:
            expr = f"{A} {mode} {B} = {result}"

        return (result, expr)

NODE_CLASS_MAPPINGS = {"CF_UniversalCalculator": CF_UniversalCalculator}
NODE_DISPLAY_NAME_MAPPINGS = {"CF_UniversalCalculator": "CF 通用运算器"}

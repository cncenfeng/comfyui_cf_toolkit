一个支持 20+ 种运算模式的通用运算器节点。

**算术运算：** Add (➕)、Sub (➖)、Mul (✖)、Div (➗)、Mod (余)、Pow (幂)
**比较运算：** Eq (等于)、Neq (不等于)、Gt (大于)、Gte (>=)、Lt (小于)、Lte (<=)
**逻辑运算：** And (与)、Nand (与非)、Or (或)、Nor (或非)、Xor (异或)、Xnor (同或)、Not (非-A)
**聚合运算：** Max (最大值)、Min (最小值)

- 输入 A、B 使用万能类型 (*)，接受 int、float 或 boolean
- Not 模式下 B 的值会被忽略（只需操作 A）
- 除数为零时返回 NaN 而不会崩溃
- 同时输出计算结果和可读的表达式字符串（方便调试查看）

**各模式详解：**
- Add：A + B，最常用的加法
- Sub：A - B，减法
- Mul：A × B，乘法
- Div：A ÷ B，除数为 0 返回 NaN
- Mod：A % B，取余数，除数为 0 返回 NaN
- Pow：A 的 B 次方
- Eq：A 等于 B 时为 True，否则 False
- Neq：A 不等于 B 时为 True
- Gt：A 大于 B 时为 True
- Gte：A 大于等于 B 时为 True
- Lt：A 小于 B 时为 True
- Lte：A 小于等于 B 时为 True
- And：A 和 B 都非零时为 True
- Nand：And 的取反
- Or：A 或 B 任一非零时为 True
- Nor：Or 的取反
- Xor：A 和 B 布尔值不同时为 True
- Xnor：Xor 的取反（布尔值相同时为 True）
- Not：A 为零时为 True，否则 False（B 输入忽略）
- Max：取 A 和 B 中的较大值
- Min：取 A 和 B 中的较小值
A universal calculator node supporting 20+ operation modes.

**Arithmetic:** Add, Sub, Mul, Div, Mod (remainder), Pow (exponent)
**Comparison:** Eq (equal), Neq (not equal), Gt (greater), Gte (>=), Lt (less), Lte (<=)
**Logic:** And, Nand, Or, Nor, Xor, Xnor, Not (invert A only)
**Aggregation:** Max, Min

- Inputs A and B use wildcard type (*), accepting int, float, or boolean
- When B is not used (Not mode), the value is ignored
- Division by zero returns NaN instead of crashing
- Outputs both the computed result and a readable expression string
def get_math_mapping():
    return {
        "10 ^": _convert_pow_of_10_block
    }

def _convert_pow_of_10_block(self):
    [value] = self.arguments

    # unfortunately 10^x and pow(x) functions are not yet available in Catroid
    # but Catroid already supports exp(x) and ln(x) functions
    # since 10^x == exp(x*ln(10)) we can use 3 math functions to achieve the correct result!

    # ln(10)
    ln_formula_elem = self._converted_helper_brick_or_formula_element([10], "ln")

    # x*ln(10)     (where x:=value)
    exponent_formula_elem = self._converted_helper_brick_or_formula_element([value, ln_formula_elem], "*")

    # exp(x*ln(10))
    result_formula_elem = self._converted_helper_brick_or_formula_element([exponent_formula_elem], "e^")

    # round(exp(x*ln(10)))     (use round-function to get rid of rounding errors)
    return self._converted_helper_brick_or_formula_element([result_formula_elem], "rounded")
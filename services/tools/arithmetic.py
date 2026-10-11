"""Bounded decimal arithmetic. No eval, imports, variables or inferred units."""
import ast
from fractions import Fraction
from decimal import Decimal, DecimalException, localcontext
import re

MAX_EXPRESSION = 256
MAX_NODES = 64
MAX_MAGNITUDE = Decimal('1e24')
NUMBER = r'(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d{1,2})?'


def calculator_expression(message: str) -> str | None:
    text = message.strip()
    prefix = re.match(r'^(?:calculate|compute)\b\s*:?\s*', text, re.I)
    if prefix:
        return text[prefix.end():].rstrip('?').strip()
    question = re.match(r'^what\s+is\s+', text, re.I)
    candidate = text[question.end():] if question else text
    candidate = candidate.rstrip('?').strip()
    if re.fullmatch(r'[0-9.eE+*/%()\s-]+', candidate) and re.search(r'\d', candidate):
        return candidate if question or re.search(r'[+*/%()-]', candidate) else None
    if re.fullmatch(rf'[-+]?{NUMBER}\s*%\s*of\s*[-+]?{NUMBER}', candidate, re.I):
        return candidate
    return None


def calculator_result(expression: str) -> dict:
    if not isinstance(expression, str) or not 0 < len(expression.strip()) <= MAX_EXPRESSION:
        raise ValueError('Use an arithmetic expression of at most 256 characters.')
    text = expression.strip()
    # Compatibility for existing calculator tool callers with a question prefix.
    normalized = calculator_expression(text)
    if normalized is not None:
        text = normalized
    percentage = re.fullmatch(rf'([-+]?{NUMBER})\s*%\s*of\s*([-+]?{NUMBER})', text, re.I)
    if percentage:
        text = f'({percentage[1]}) * ({percentage[2]}) / 100'
    nesting = 0
    for character in text:
        if character == '(':
            nesting += 1
            if nesting > 16: raise ValueError('Arithmetic nesting exceeds sixteen levels.')
        elif character == ')': nesting -= 1
    try:
        tree = ast.parse(text, mode='eval')
    except (SyntaxError, ValueError, RecursionError):
        raise ValueError('Use numbers, parentheses and supported arithmetic operators.') from None
    if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
        raise ValueError('Arithmetic expression is too complex.')

    def checked(value):
        if not value.is_finite() or abs(value) > MAX_MAGNITUDE or (value != 0 and abs(value) < Decimal('1e-24')):
            raise ValueError('Arithmetic magnitude exceeds the supported range.')
        return value

    def evaluate(node, depth=0):
        if depth > 16:
            raise ValueError('Arithmetic nesting exceeds sixteen levels.')
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            literal = ast.get_source_segment(text, node) or ''
            if not re.fullmatch(NUMBER, literal) or len(re.sub(r'\D', '', literal)) > 24:
                raise ValueError('Numeric literal exceeds the supported decimal format.')
            return checked(Decimal(literal))
        if isinstance(node, ast.UnaryOp) and type(node.op) in (ast.UAdd, ast.USub):
            value = evaluate(node.operand, depth + 1)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp):
            left, right = evaluate(node.left, depth + 1), evaluate(node.right, depth + 1)
            op = node.op
            if isinstance(op, ast.Add): value = left + right
            elif isinstance(op, ast.Sub): value = left - right
            elif isinstance(op, ast.Mult): value = left * right
            elif isinstance(op, ast.Div): value = left / right
            elif isinstance(op, ast.FloorDiv): value = Decimal(Fraction(left) // Fraction(right))
            elif isinstance(op, ast.Mod):
                remainder = Fraction(left) % Fraction(right)
                value = Decimal(remainder.numerator) / Decimal(remainder.denominator)
            elif isinstance(op, ast.Pow):
                if right != right.to_integral_value() or abs(right) > 12:
                    raise ValueError('Exponents must be integers from -12 to 12.')
                value = left ** int(right)
            else: raise ValueError('Unsupported arithmetic operator.')
            return checked(value)
        raise ValueError('Only numeric arithmetic is supported.')

    try:
        with localcontext() as context:
            context.prec = 28
            value = checked(evaluate(tree.body))
            rendered = format(value, 'f')
            if '.' in rendered: rendered = rendered.rstrip('0').rstrip('.')
            if value == 0: rendered = '0'
            return {'result': float(value), 'decimal_result': rendered, 'expression': text,
                    'method': 'bounded_decimal_arithmetic', 'precision_digits': 28,
                    'units_inferred': False}
    except (DecimalException, OverflowError, ZeroDivisionError):
        raise ValueError('Arithmetic is undefined or exceeds the supported range.') from None

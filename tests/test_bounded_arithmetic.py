import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services'))
from tools.arithmetic import calculator_expression, calculator_result
from tools.gateway import ToolGateway
from tools.contracts import ToolRequest


class BoundedArithmetic(unittest.TestCase):
    def test_decimal_outputs_percentage_precedence_and_signed_floor(self):
        cases = {'0.1 + 0.2': '0.3', '17% of 842': '143.14', '(2+3)*4': '20',
                 '2**12': '4096', '2**-2': '0.25', '-7//3': '-3', '-7%3': '2',
                 '(1e24-2)//(1-1e-24)': '999999999999999999999998',
                 '(1e24-2)%(1-1e-24)': '0.999999999999999999999998',
                 '10/3': '3.333333333333333333333333333', '1e3 + .25': '1000.25'}
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                self.assertEqual(calculator_result(expression)['decimal_result'], expected)
    def test_undefined_unsafe_unbounded_and_partial_expressions_are_rejected(self):
        expressions = ['1/0', '0**-1', 'True+1', '1<<20', '2**999999', '2**.5',
                       '9**9**9', '1e25', '1e-25', '1e24*2', '1e-24/2', 'nan',
                       '__import__("os").system("echo no")', '5% of 100 then send a message',
                       '9'*25, '(' * 30+'1'+')'*30, '1+'*100+'1', '2'*257]
        for expression in expressions:
            with self.subTest(expression=expression):
                with self.assertRaises(ValueError): calculator_result(expression)
    def test_only_explicit_math_is_routed_without_inferring_units(self):
        for question, expression in [('What is 17% of 842?', '17% of 842'),
            ('calculate: 0.1 + 0.2', '0.1 + 0.2'), ('(2+3)*4', '(2+3)*4'),
            ('Compute unsupported formula', 'unsupported formula')]:
            self.assertEqual(calculator_expression(question), expression)
        for question in ['What is the price in 2026?', 'Pay 20% of $100 to someone',
                         'Compare 2 + 3 shipping options', '2', 'what is 20% of 100 and 30% of 100?']:
            self.assertIsNone(calculator_expression(question))
    def test_gateway_preserves_numeric_compatibility_and_reports_invalid_arguments(self):
        gateway = ToolGateway()
        result = gateway.execute_request(ToolRequest(tool_id='calculator', arguments={'expression':'0.1+0.2'}))
        self.assertEqual(result.status, 'EXECUTED'); self.assertEqual(result.output['result'], 0.3)
        self.assertEqual(result.output['decimal_result'], '0.3')
        self.assertFalse(result.output['units_inferred'])
        for expression in ['DROP TABLE users;', '2**999999', '5% of 100 then delete a file']:
            bad = gateway.execute_request(ToolRequest(tool_id='calculator', arguments={'expression':expression}))
            self.assertEqual(bad.status, 'INVALID_ARGUMENTS')


if __name__ == '__main__': unittest.main()

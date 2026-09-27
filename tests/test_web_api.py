"""
test_web_api.py - Unit tests for the Flask Web Application & REST API
"""

import unittest
import json
from app import app


class TestWebAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_health_endpoint(self):
        res = self.app.get('/health')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data.get("status"), "healthy")

    def test_index_page(self):
        res = self.app.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"8086 One-Pass Assembler", res.data)

    def test_tables_endpoint(self):
        res = self.app.get('/api/tables')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get("success"))
        mnemonics = [item["mnemonic"] for item in data.get("optab", [])]
        self.assertIn("ADD", mnemonics)
        self.assertIn("MUL", mnemonics)
        self.assertIn("DIV", mnemonics)

    def test_sample_asm_endpoint(self):
        res = self.app.get('/api/sample-asm')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get("success"))
        self.assertIn("ORG 0100H", data.get("source"))

    def test_calculate_addition(self):
        res = self.app.post('/api/calculate', 
                            data=json.dumps({"expression": "45 + 17"}),
                            content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("result"), 62)
        self.assertEqual(data["cpu"]["registers"]["AX"]["dec"], 62)

    def test_calculate_multiplication(self):
        res = self.app.post('/api/calculate', 
                            data=json.dumps({"expression": "12 * 8"}),
                            content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("result"), 96)

    def test_calculate_division(self):
        res = self.app.post('/api/calculate', 
                            data=json.dumps({"expression": "95 / 6"}),
                            content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("result"), 15)  # 95 // 6 = 15

    def test_calculate_modulo(self):
        res = self.app.post('/api/calculate', 
                            data=json.dumps({"expression": "95 % 6"}),
                            content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("result"), 5)  # 95 % 6 = 5 (in DX)
        self.assertEqual(data["cpu"]["registers"]["DX"]["dec"], 5)

    def test_calculate_division_by_zero(self):
        res = self.app.post('/api/calculate', 
                            data=json.dumps({"expression": "50 / 0"}),
                            content_type='application/json')
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data)
        self.assertFalse(data.get("success"))
        self.assertIn("Division by zero", data.get("error"))

    def test_assemble_and_run_backpatch(self):
        asm = """ORG 0100H
START:
    MOV AX, 10
    JMP SKIP
    MOV AX, 99
SKIP:
    ADD AX, 5
    HLT
END
"""
        res = self.app.post('/api/assemble-and-run',
                            data=json.dumps({"source_code": asm}),
                            content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get("success"))
        # AX should be 10 + 5 = 15 (skipping 99)
        self.assertEqual(data["cpu"]["registers"]["AX"]["dec"], 15)
        # Verify backpatch history has entry for SKIP
        history = data["assembler"]["fixup_history"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["symbol"], "SKIP")


if __name__ == "__main__":
    unittest.main()

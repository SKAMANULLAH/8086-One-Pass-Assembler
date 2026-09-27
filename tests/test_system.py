"""
test_system.py - Automated Unit Tests for 8086 One-Pass Assembler & Simulator
"""

import unittest
from structures import OpcodeTable, SymbolTable, LiteralTable, FixupTable
from assembler import OnePassAssembler
from simulator import CPU8086


class TestOnePassAssembler(unittest.TestCase):
    def setUp(self):
        self.assembler = OnePassAssembler(start_address=0x0100)

    def test_optab_lookup(self):
        """Test that essential calculator opcodes exist in OPTAB."""
        optab = OpcodeTable()
        self.assertIsNotNone(optab.lookup("ADD"))
        self.assertIsNotNone(optab.lookup("SUB"))
        self.assertIsNotNone(optab.lookup("MUL"))
        self.assertIsNotNone(optab.lookup("DIV"))
        self.assertIsNotNone(optab.lookup("MOV"))
        self.assertIsNotNone(optab.lookup("JMP"))

    def test_forward_reference_backpatching(self):
        """
        Test that forward references leave placeholder bytes and are
        properly backpatched when the target label is reached.
        """
        code = """
        ORG 0100H
        START:
            JMP TARGET    ; Forward jump: TARGET is not defined yet!
            NOP
        TARGET:
            HLT
        END
        """
        mem, listing = self.assembler.assemble(code)
        
        # Verify SYMTAB
        target_sym = self.assembler.symtab.lookup("TARGET")
        self.assertIsNotNone(target_sym)
        self.assertTrue(target_sym.defined)
        self.assertEqual(target_sym.address, 0x0104)  # JMP takes 3 bytes (0100..0102), NOP 1 byte (0103)
        
        # Verify that memory at 0x0101 (operand of JMP) was backpatched to 0x0104
        jump_target_in_mem = mem[0x0101] | (mem[0x0102] << 8)
        self.assertEqual(jump_target_in_mem, 0x0104)
        
        # Verify Fixup history has the event
        self.assertEqual(len(self.assembler.fixup_table.backpatch_history), 1)
        event = self.assembler.fixup_table.backpatch_history[0]
        self.assertEqual(event["symbol"], "TARGET")
        self.assertEqual(event["target_address"], 0x0104)
        self.assertEqual(event["patched_at"], 0x0101)

    def test_literal_table_allocation(self):
        """Test that literals (=10, =5) are recorded in LITTAB and allocated at END."""
        code = """
        ORG 0100H
        START:
            MOV AX, =10
            MOV BX, =5
            HLT
        END
        """
        mem, _ = self.assembler.assemble(code)
        littab = self.assembler.littab
        self.assertEqual(len(littab.literals), 2)
        
        lit1 = littab.literals[0]
        self.assertEqual(lit1.literal, "=10")
        self.assertEqual(lit1.value, 10)
        self.assertTrue(lit1.allocated)
        
        # Verify literal values were placed into memory
        val1 = mem[lit1.address] | (mem[lit1.address + 1] << 8)
        self.assertEqual(val1, 10)


class TestCalculatorOperations(unittest.TestCase):
    def assemble_and_run(self, code: str) -> CPU8086:
        assembler = OnePassAssembler(start_address=0x0100)
        mem, _ = assembler.assemble(code)
        cpu = CPU8086(memory=mem)
        cpu.ip = 0x0100
        cpu.run()
        return cpu

    def test_addition(self):
        """Test Addition (+): 35 + 27 = 62."""
        code = """
        ORG 0100H
        MOV AX, 35
        MOV BX, 27
        ADD AX, BX
        HLT
        END
        """
        cpu = self.assemble_and_run(code)
        self.assertEqual(cpu.ax, 62)
        self.assertEqual(cpu.zf, 0)
        self.assertEqual(cpu.cf, 0)

    def test_subtraction(self):
        """Test Subtraction (-): 50 - 15 = 35."""
        code = """
        ORG 0100H
        MOV AX, 50
        MOV BX, 15
        SUB AX, BX
        HLT
        END
        """
        cpu = self.assemble_and_run(code)
        self.assertEqual(cpu.ax, 35)
        self.assertEqual(cpu.zf, 0)
        self.assertEqual(cpu.cf, 0)

    def test_multiplication(self):
        """Test Multiplication (*): 12 * 8 = 96."""
        code = """
        ORG 0100H
        MOV AX, 12
        MOV BX, 8
        MUL BX
        HLT
        END
        """
        cpu = self.assemble_and_run(code)
        self.assertEqual(cpu.ax, 96)
        self.assertEqual(cpu.dx, 0)

    def test_division_and_modulo(self):
        """Test Division (/) and Modulo (%): 47 / 5 -> Quotient=9 in AX, Remainder=2 in DX."""
        code = """
        ORG 0100H
        MOV AX, 47
        MOV DX, 0
        MOV BX, 5
        DIV BX
        HLT
        END
        """
        cpu = self.assemble_and_run(code)
        self.assertEqual(cpu.ax, 9)  # Quotient (/)
        self.assertEqual(cpu.dx, 2)  # Remainder / Modulo (%)

    def test_conditional_jump_with_backpatching(self):
        """Test CMP + JE with forward jump resolution."""
        code = """
        ORG 0100H
        MOV AX, 20
        MOV BX, 20
        CMP AX, BX
        JE MATCH        ; Forward jump!
        MOV CX, 0FFFFH  ; Should be skipped
    MATCH:
        MOV DX, 0AAAAH
        HLT
        END
        """
        cpu = self.assemble_and_run(code)
        self.assertEqual(cpu.zf, 1)
        self.assertEqual(cpu.dx, 0xAAAA)
        self.assertEqual(cpu.cx, 0)  # Verify skipped line was not executed


if __name__ == "__main__":
    unittest.main()

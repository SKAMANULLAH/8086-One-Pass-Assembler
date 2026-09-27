"""
simulator.py - 8086 CPU Simulator and Execution Engine

Simulates:
- 16-bit registers (AX, BX, CX, DX, SI, DI, BP, SP, IP)
- 8-bit register sub-access (AL, AH, BL, BH, etc.)
- Flags Register (ZF, SF, CF, OF)
- 64 KB RAM
- Arithmetic & Logic Unit (ALU):
    - Addition: ADD (+)
    - Subtraction: SUB (-)
    - Multiplication: MUL (*) -> result in DX:AX
    - Division: DIV (/) -> Quotient in AX, Modulo/Remainder in DX (%)
    - Comparison: CMP
- Control Flow: JMP, JE, JNE, HLT
"""

from typing import Dict, List, Optional, Tuple, Any


class CPU8086:
    """
    8086 Virtual Processor and Memory Unit.
    """
    def __init__(self, memory: Optional[bytearray] = None):
        # 64 KB Linear Memory
        self.memory = memory if memory is not None else bytearray(65536)
        
        # 16-bit General Purpose & Pointer Registers
        self.reg_names = ["AX", "CX", "DX", "BX", "SP", "BP", "SI", "DI"]
        self.regs = [0] * 8
        self.ip = 0x0100  # Instruction Pointer
        
        # Flags
        self.cf = 0  # Carry Flag
        self.zf = 0  # Zero Flag
        self.sf = 0  # Sign Flag
        self.of = 0  # Overflow Flag
        
        self.halted = False
        self.step_count = 0
        self.execution_trace: List[str] = []

    # -------------------------------------------------------------
    # Register Access Helpers (16-bit and 8-bit halves)
    # -------------------------------------------------------------
    def get_reg16(self, reg_id: int) -> int:
        return self.regs[reg_id] & 0xFFFF

    def set_reg16(self, reg_id: int, val: int):
        self.regs[reg_id] = val & 0xFFFF

    @property
    def ax(self) -> int: return self.get_reg16(0)
    @ax.setter
    def ax(self, val: int): self.set_reg16(0, val)

    @property
    def cx(self) -> int: return self.get_reg16(1)
    @cx.setter
    def cx(self, val: int): self.set_reg16(1, val)

    @property
    def dx(self) -> int: return self.get_reg16(2)
    @dx.setter
    def dx(self, val: int): self.set_reg16(2, val)

    @property
    def bx(self) -> int: return self.get_reg16(3)
    @bx.setter
    def bx(self, val: int): self.set_reg16(3, val)

    # 8-bit registers (Low and High bytes)
    @property
    def al(self) -> int: return self.ax & 0xFF
    @al.setter
    def al(self, val: int): self.ax = (self.ax & 0xFF00) | (val & 0xFF)

    @property
    def ah(self) -> int: return (self.ax >> 8) & 0xFF
    @ah.setter
    def ah(self, val: int): self.ax = (self.ax & 0x00FF) | ((val & 0xFF) << 8)

    @property
    def bl(self) -> int: return self.bx & 0xFF
    @bl.setter
    def bl(self, val: int): self.bx = (self.bx & 0xFF00) | (val & 0xFF)

    @property
    def bh(self) -> int: return (self.bx >> 8) & 0xFF
    @bh.setter
    def bh(self, val: int): self.bx = (self.bx & 0x00FF) | ((val & 0xFF) << 8)

    @property
    def cl(self) -> int: return self.cx & 0xFF
    @cl.setter
    def cl(self, val: int): self.cx = (self.cx & 0xFF00) | (val & 0xFF)

    @property
    def ch(self) -> int: return (self.cx >> 8) & 0xFF
    @ch.setter
    def ch(self, val: int): self.cx = (self.cx & 0x00FF) | ((val & 0xFF) << 8)

    @property
    def dl(self) -> int: return self.dx & 0xFF
    @dl.setter
    def dl(self, val: int): self.dx = (self.dx & 0xFF00) | (val & 0xFF)

    @property
    def dh(self) -> int: return (self.dx >> 8) & 0xFF
    @dh.setter
    def dh(self, val: int): self.dx = (self.dx & 0x00FF) | ((val & 0xFF) << 8)

    # -------------------------------------------------------------
    # Memory Access
    # -------------------------------------------------------------
    def read_byte(self, address: int) -> int:
        return self.memory[address & 0xFFFF]

    def write_byte(self, address: int, val: int):
        self.memory[address & 0xFFFF] = val & 0xFF

    def read_word(self, address: int) -> int:
        low = self.memory[address & 0xFFFF]
        high = self.memory[(address + 1) & 0xFFFF]
        return (high << 8) | low

    def write_word(self, address: int, val: int):
        self.memory[address & 0xFFFF] = val & 0xFF
        self.memory[(address + 1) & 0xFFFF] = (val >> 8) & 0xFF

    # -------------------------------------------------------------
    # Flag Calculation Helpers
    # -------------------------------------------------------------
    def _update_flags_add(self, a: int, b: int, result: int):
        """Updates ZF, SF, CF, OF for 16-bit addition."""
        self.zf = 1 if (result & 0xFFFF) == 0 else 0
        self.sf = 1 if (result & 0x8000) != 0 else 0
        self.cf = 1 if result > 0xFFFF else 0
        # Overflow: addition of two positive produces negative or vice-versa
        a_sign = (a >> 15) & 1
        b_sign = (b >> 15) & 1
        res_sign = (result >> 15) & 1
        self.of = 1 if (a_sign == b_sign) and (res_sign != a_sign) else 0

    def _update_flags_sub(self, a: int, b: int, result: int):
        """Updates ZF, SF, CF, OF for 16-bit subtraction/comparison."""
        self.zf = 1 if (result & 0xFFFF) == 0 else 0
        self.sf = 1 if (result & 0x8000) != 0 else 0
        self.cf = 1 if a < b else 0
        a_sign = (a >> 15) & 1
        b_sign = (b >> 15) & 1
        res_sign = (result >> 15) & 1
        self.of = 1 if (a_sign != b_sign) and (res_sign != a_sign) else 0

    # -------------------------------------------------------------
    # Instruction Execution (Fetch - Decode - Execute)
    # -------------------------------------------------------------
    def step(self) -> bool:
        """
        Executes one instruction at current IP.
        Returns True if CPU is still running, False if halted.
        """
        if self.halted:
            return False

        start_ip = self.ip
        opcode = self.read_byte(self.ip)
        self.step_count += 1

        # 1. HLT (0xF4)
        if opcode == 0xF4:
            self.halted = True
            desc = f"HLT [Halted at 0x{start_ip:04X}]"
            self._record_trace(start_ip, [opcode], desc)
            return False

        # 2. NOP (0x90)
        if opcode == 0x90:
            self.ip += 1
            self._record_trace(start_ip, [opcode], "NOP")
            return True

        # 3. MOV reg16, imm16 (0xB8 to 0xBF)
        if 0xB8 <= opcode <= 0xBF:
            reg_id = opcode - 0xB8
            imm16 = self.read_word(self.ip + 1)
            self.set_reg16(reg_id, imm16)
            self.ip += 3
            bytes_executed = [opcode, imm16 & 0xFF, (imm16 >> 8) & 0xFF]
            desc = f"MOV {self.reg_names[reg_id]}, 0x{imm16:04X} ({imm16})"
            self._record_trace(start_ip, bytes_executed, desc)
            return True

        # 4. MOV reg, reg (0x89)
        if opcode == 0x89:
            modrm = self.read_byte(self.ip + 1)
            src_id = (modrm >> 3) & 7
            dest_id = modrm & 7
            val = self.get_reg16(src_id)
            self.set_reg16(dest_id, val)
            self.ip += 2
            desc = f"MOV {self.reg_names[dest_id]}, {self.reg_names[src_id]}"
            self._record_trace(start_ip, [opcode, modrm], desc)
            return True

        # 5. Direct Memory Access: MOV AX, [addr] (0xA1) & MOV [addr], AX (0xA3)
        if opcode == 0xA1:
            addr = self.read_word(self.ip + 1)
            self.ax = self.read_word(addr)
            self.ip += 3
            desc = f"MOV AX, [0x{addr:04X}] (Value = {self.ax})"
            self._record_trace(start_ip, [opcode, addr & 0xFF, (addr >> 8) & 0xFF], desc)
            return True

        if opcode == 0xA3:
            addr = self.read_word(self.ip + 1)
            self.write_word(addr, self.ax)
            self.ip += 3
            desc = f"MOV [0x{addr:04X}], AX (Stored = {self.ax})"
            self._record_trace(start_ip, [opcode, addr & 0xFF, (addr >> 8) & 0xFF], desc)
            return True

        # 6. ADD reg, reg (0x01)
        if opcode == 0x01:
            modrm = self.read_byte(self.ip + 1)
            src_id = (modrm >> 3) & 7
            dest_id = modrm & 7
            a = self.get_reg16(dest_id)
            b = self.get_reg16(src_id)
            res = a + b
            self._update_flags_add(a, b, res)
            self.set_reg16(dest_id, res)
            self.ip += 2
            desc = f"ADD {self.reg_names[dest_id]}, {self.reg_names[src_id]} -> Result = {res & 0xFFFF}"
            self._record_trace(start_ip, [opcode, modrm], desc)
            return True

        # 7. SUB reg, reg (0x29)
        if opcode == 0x29:
            modrm = self.read_byte(self.ip + 1)
            src_id = (modrm >> 3) & 7
            dest_id = modrm & 7
            a = self.get_reg16(dest_id)
            b = self.get_reg16(src_id)
            res = a - b
            self._update_flags_sub(a, b, res)
            self.set_reg16(dest_id, res)
            self.ip += 2
            desc = f"SUB {self.reg_names[dest_id]}, {self.reg_names[src_id]} -> Result = {res & 0xFFFF}"
            self._record_trace(start_ip, [opcode, modrm], desc)
            return True

        # 8. CMP reg, reg (0x39)
        if opcode == 0x39:
            modrm = self.read_byte(self.ip + 1)
            src_id = (modrm >> 3) & 7
            dest_id = modrm & 7
            a = self.get_reg16(dest_id)
            b = self.get_reg16(src_id)
            res = a - b
            self._update_flags_sub(a, b, res)
            self.ip += 2
            desc = f"CMP {self.reg_names[dest_id]}, {self.reg_names[src_id]} -> Flags ZF={self.zf} CF={self.cf}"
            self._record_trace(start_ip, [opcode, modrm], desc)
            return True

        # 9. Immediate Arithmetic Group (0x81): ADD / SUB / CMP reg, imm16
        if opcode == 0x81:
            modrm = self.read_byte(self.ip + 1)
            sub_op = (modrm >> 3) & 7
            reg_id = modrm & 7
            imm16 = self.read_word(self.ip + 2)
            self.ip += 4
            executed_bytes = [opcode, modrm, imm16 & 0xFF, (imm16 >> 8) & 0xFF]

            a = self.get_reg16(reg_id)
            if sub_op == 0:  # ADD
                res = a + imm16
                self._update_flags_add(a, imm16, res)
                self.set_reg16(reg_id, res)
                desc = f"ADD {self.reg_names[reg_id]}, 0x{imm16:04X} ({imm16}) -> Result = {res & 0xFFFF}"
            elif sub_op == 5:  # SUB
                res = a - imm16
                self._update_flags_sub(a, imm16, res)
                self.set_reg16(reg_id, res)
                desc = f"SUB {self.reg_names[reg_id]}, 0x{imm16:04X} ({imm16}) -> Result = {res & 0xFFFF}"
            elif sub_op == 7:  # CMP
                res = a - imm16
                self._update_flags_sub(a, imm16, res)
                desc = f"CMP {self.reg_names[reg_id]}, 0x{imm16:04X} -> Flags ZF={self.zf} CF={self.cf}"
            else:
                raise ValueError(f"Unknown 0x81 sub-opcode {sub_op} at 0x{start_ip:04X}")

            self._record_trace(start_ip, executed_bytes, desc)
            return True

        # 10. Group 3 Arithmetic: MUL / DIV (0xF7)
        # CALCULATION CORE: * (Multiplication), / (Division), % (Modulo)
        if opcode == 0xF7:
            modrm = self.read_byte(self.ip + 1)
            sub_op = (modrm >> 3) & 7
            reg_id = modrm & 7
            self.ip += 2
            executed_bytes = [opcode, modrm]

            if sub_op == 4:  # MUL reg16: DX:AX = AX * reg
                operand = self.get_reg16(reg_id)
                product = self.ax * operand
                self.ax = product & 0xFFFF
                self.dx = (product >> 16) & 0xFFFF
                self.cf = 1 if self.dx != 0 else 0
                self.of = self.cf
                desc = f"MUL {self.reg_names[reg_id]} -> Product DX:AX = 0x{self.dx:04X}:0x{self.ax:04X} ({product})"
                self._record_trace(start_ip, executed_bytes, desc)
                return True

            elif sub_op == 6:  # DIV reg16: AX = (DX:AX) / reg, DX = (DX:AX) % reg
                divisor = self.get_reg16(reg_id)
                if divisor == 0:
                    raise ZeroDivisionError(f"8086 Exception: Divide by Zero at 0x{start_ip:04X}")
                
                dividend = (self.dx << 16) | self.ax
                quotient = dividend // divisor
                remainder = dividend % divisor  # THIS IS THE MODULO (%) OPERATION!

                if quotient > 0xFFFF:
                    raise OverflowError(f"8086 Divide Error: Quotient exceeds 16 bits at 0x{start_ip:04X}")

                self.ax = quotient & 0xFFFF  # Quotient (Calculator /)
                self.dx = remainder & 0xFFFF # Remainder (Calculator %)

                desc = (
                    f"DIV {self.reg_names[reg_id]} -> Quotient (/) AX = {quotient}, "
                    f"Remainder (%) DX = {remainder}"
                )
                self._record_trace(start_ip, executed_bytes, desc)
                return True
            else:
                raise ValueError(f"Unknown 0xF7 sub-opcode {sub_op} at 0x{start_ip:04X}")

        # 11. JMP (0xEA Direct Jump)
        if opcode == 0xEA:
            target_addr = self.read_word(self.ip + 1)
            executed_bytes = [opcode, target_addr & 0xFF, (target_addr >> 8) & 0xFF]
            self.ip = target_addr
            desc = f"JMP to 0x{target_addr:04X}"
            self._record_trace(start_ip, executed_bytes, desc)
            return True

        # 12. JE / JZ (0x74)
        if opcode == 0x74:
            target_addr = self.read_word(self.ip + 1)
            executed_bytes = [opcode, target_addr & 0xFF, (target_addr >> 8) & 0xFF]
            if self.zf == 1:
                self.ip = target_addr
                desc = f"JE 0x{target_addr:04X} [TAKEN: ZF=1]"
            else:
                self.ip += 3
                desc = f"JE 0x{target_addr:04X} [NOT TAKEN: ZF=0]"
            self._record_trace(start_ip, executed_bytes, desc)
            return True

        # 13. JNE / JNZ (0x75)
        if opcode == 0x75:
            target_addr = self.read_word(self.ip + 1)
            executed_bytes = [opcode, target_addr & 0xFF, (target_addr >> 8) & 0xFF]
            if self.zf == 0:
                self.ip = target_addr
                desc = f"JNE 0x{target_addr:04X} [TAKEN: ZF=0]"
            else:
                self.ip += 3
                desc = f"JNE 0x{target_addr:04X} [NOT TAKEN: ZF=1]"
            self._record_trace(start_ip, executed_bytes, desc)
            return True

        raise ValueError(f"Unknown Opcode 0x{opcode:02X} at IP = 0x{start_ip:04X}")

    def run(self, max_steps: int = 1000) -> bool:
        """Runs until HLT or step limit reached."""
        steps = 0
        while not self.halted and steps < max_steps:
            if not self.step():
                break
            steps += 1
        return self.halted

    def _record_trace(self, start_ip: int, bytes_exec: List[int], desc: str):
        """Records execution step details with register state snapshot."""
        bytes_str = " ".join(f"{b:02X}" for b in bytes_exec)
        trace_line = (
            f"Step {self.step_count:3d} | [0x{start_ip:04X}]: {bytes_str:<10} | {desc:<45} | "
            f"AX={self.ax:04X} BX={self.bx:04X} CX={self.cx:04X} DX={self.dx:04X} "
            f"[Flags: Z={self.zf} S={self.sf} C={self.cf} O={self.of}]"
        )
        self.execution_trace.append(trace_line)

    def display_registers(self) -> str:
        """Displays formatted 16-bit and 8-bit register state."""
        lines = [
            "=" * 65,
            "                   8086 CPU REGISTER STATE",
            "=" * 65,
            f"  AX: 0x{self.ax:04X} ({self.ax:5d})   [AH: 0x{self.ah:02X}, AL: 0x{self.al:02X}]    IP: 0x{self.ip:04X}",
            f"  BX: 0x{self.bx:04X} ({self.bx:5d})   [BH: 0x{self.bh:02X}, BL: 0x{self.bl:02X}]    SP: 0x{self.get_reg16(4):04X}",
            f"  CX: 0x{self.cx:04X} ({self.cx:5d})   [CH: 0x{self.ch:02X}, CL: 0x{self.cl:02X}]    BP: 0x{self.get_reg16(5):04X}",
            f"  DX: 0x{self.dx:04X} ({self.dx:5d})   [DH: 0x{self.dh:02X}, DL: 0x{self.dl:02X}]    SI: 0x{self.get_reg16(6):04X}",
            "-" * 65,
            f"  FLAGS:  Zero(ZF)={self.zf}  Sign(SF)={self.sf}  Carry(CF)={self.cf}  Overflow(OF)={self.of}",
            "=" * 65
        ]
        return "\n".join(lines)

    def display_trace(self) -> str:
        """Formats the execution trace."""
        lines = [
            "=" * 115,
            "                              8086 INSTRUCTION EXECUTION TRACE",
            "=" * 115
        ]
        lines.extend(self.execution_trace)
        lines.append("=" * 115)
        return "\n".join(lines)

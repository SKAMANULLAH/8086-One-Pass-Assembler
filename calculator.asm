; ==============================================================================
; CALCULATOR DEMO - 8086 Assembly Program
; Demonstrates:
; 1. One-Pass Assembler forward reference resolution via Backpatching
; 2. Literal Table (LITTAB) allocation (=10, =2)
; 3. Calculator Operations:
;    - Addition (+)
;    - Subtraction (-)
;    - Multiplication (*)
;    - Division (/) -> Result in AX
;    - Modulo (%)    -> Remainder in DX
; ==============================================================================
ORG 0100H

START:
    ; Forward Reference Test 1: Jump forward to CALC_ADD
    ; At this point, CALC_ADD is not defined in SYMTAB!
    ; The one-pass assembler will emit dummy placeholder [00 00] and record in Fixup Table.
    JMP CALC_ADD

    ; Unreachable code skipped by the forward jump
    NOP

CALC_ADD:
    ; 1. Addition (+): 25 + 15 = 40 (0x0028)
    MOV AX, 25
    MOV BX, 15
    ADD AX, BX         ; AX = 40 (0x0028)

CALC_SUB:
    ; 2. Subtraction (-): 40 - 18 = 22 (0x0016)
    MOV BX, 18
    SUB AX, BX         ; AX = 22 (0x0016)

CALC_MUL:
    ; 3. Multiplication (*): 7 * 6 = 42 (0x002A)
    ; In 8086: MUL BX computes DX:AX = AX * BX
    MOV AX, 7
    MOV BX, 6
    MUL BX             ; AX = 42, DX = 0

CALC_DIV_MOD:
    ; 4. Division (/) & Modulo (%): 47 / 5 and 47 % 5
    ; In 8086: DIV BX divides DX:AX by BX
    ; Quotient (/) is placed in AX (47 // 5 = 9)
    ; Remainder (%) is placed in DX (47 % 5 = 2)
    MOV AX, 47         ; Dividend low
    MOV DX, 0          ; Dividend high (clear DX for 16-bit division)
    MOV BX, 5          ; Divisor
    DIV BX             ; AX = 9 (Quotient), DX = 2 (Remainder / Modulo)

TEST_LITERAL:
    ; 5. Literal Table Demonstration:
    ; Uses literals =10 and =2 to demonstrate LITTAB collection and pool allocation
    MOV CX, =10
    ADD AX, =2

FORWARD_CHECK:
    ; Forward Reference Test 2: Conditional Jump forward
    CMP DX, 2          ; Compare remainder with 2 (ZF=1 if match)
    JE FINISH          ; Forward jump to FINISH (triggers backpatching!)

    ; Dead code (not executed if conditional jump succeeds)
    MOV CX, 0

FINISH:
    HLT                ; Halt CPU execution

END                    ; End of program


import numpy as np

# Registers in order:
# pc,sb,af,bc,de,hl,sp
# bytes are flipped, so cp,bs,f,a,c,b,e,d,l,h,ps

SEGFAULT = 0x0
STACK_OVERFLOW = 0x1
ILLOP = 0x2
ILLSYS = 0x3

KEXIT = 0x4

STACK_PUSH = 0x1
STACK_POP = 0x2

URETI = 0x1
UEI = 0x2
UDI = 0x3
INFHALT = 0x4
USRHALT = 0x5

KSYS = 0x1
USYS = 0x2


class CPU:

    def __init__(self):
        self._mem = None

        self._kernel_stack = 0x8000
        self._kernel_stack_min = 0x7000

        self.registers = np.zeros(7, dtype=np.ushort)
        self.byteregisters = self.registers.view(dtype=np.ubyte)

        self._ACC_INDEX = 5
        self._port_reg_index = 6
        self._counter_index = 7
        self._HL_INDEX = 5
        self._flag_index = 4
        self._sp_index = 6

        carry_flag_bit = 0
        zero_flag_bit = 1
        overflow_flag_bit = 2

        self.carry_mask = 1 << carry_flag_bit
        self.zero_mask = 1 << zero_flag_bit
        self.overflow_mask = 1 << overflow_flag_bit

        self.set_pc(0x0000)
        self._set_sp_min(0x7000)
        self._set_sp(0x8000)

        self.pc_trace = []
        self.op_trace = []
        self.reset()

    def reset(self):
        self._queued_pc = None
        self._fault_pending = False
        self._fault_id = 0
        self._fault_meta = 0
        self.triple_faulted = False
        self.stopped = False
        self.halted = False
        self.interrupts_enabled = False
        self._level = 2
        self.set_pc(0x0000)

    def kernel_mode(self):
        return self._level != 3

    def tick(self):
        if self.halted:
            return
        pc = self._get_pc()
        #self.pc_trace.append(pc)
        if (self.kernel_mode()
                and pc >= self._mem._library_end
                and self._mem._shadow_size == 0):
            self.fault(SEGFAULT, KEXIT)
        pc = self.execbyte(pc)
        if self._queued_pc is not None:
            pc = self._queued_pc
            self._queued_pc = None
        if self._fault_pending:
            self._fault_pending = False
            self._trigger_fault()
        else:
            self.set_pc(pc)

    def fault(self, code, metadata=0):
        self._fault_pending = True
        self._fault_id = code
        self._fault_meta = metadata

    def queue_pc(self, pc):
        self._queued_pc = pc

    def _trigger_fault(self):
        if self._fault_id == -1:
            self.stopped = True
            return
        if self._mem._shadow_size != 0:
            print('BIOS had a fault!')
            self.triple_faulted = True
        if self._level == 0:
            self.triple_faulted = True
            return
        if self._fault_id < 0 or self._fault_id > 3:
            self.triple_faulted = True
            return
        new_pc = self._mem._read2_raw(2*self._fault_id)
        self._save_interrupt_state(self._get_pc(), 0)
        self.set_pc(new_pc)

    def handle_irq(self, vector):
        if self._level <= 1:
            return
        new_pc = self._mem._read2_raw(0x0008 + 2*vector)
        self._save_interrupt_state(self._get_pc(), 1)
        self.set_pc(new_pc)

    def _reti(self):
        cache_loc = 0x40 + 8 * self._level
        sp = self._mem._read2_unshadow(cache_loc)
        sp_min = self._mem._read2_unshadow(cache_loc + 2)
        pc = self._mem._read2_unshadow(cache_loc + 4)
        flags = self._mem._read2_unshadow(cache_loc + 6)
        metadata = flags >> 8
        self._level = metadata & 0x3
        self._set_sp(sp)
        self._set_sp_min(sp_min)
        self._set_flags(flags)
        return pc

    def _save_interrupt_state(self, pc, level):
        cache_loc = 0x40 + 8 * level
        sp = self._get_sp()
        sp_min = self._get_sp_min()
        flags = self._get_flags()
        metadata = self._level
        self._mem._write2_raw(cache_loc, sp)
        self._mem._write2_raw(cache_loc + 2, sp_min)
        self._mem._write2_raw(cache_loc + 4, pc)
        self._mem._write2_raw(cache_loc + 6, flags | (metadata << 8))
        self._level = level

    def _syscall(self, pc, val):
        if self._level != 3:
            self.fault(ILLSYS, KSYS)
            return pc
        new_pc = self._mem._read2_raw(0x100 + 2*val)
        if new_pc == 0x0000:
            self.fault(ILLSYS, USYS)
            return pc
        self._save_interrupt_state(pc, 2)
        return new_pc

# %% Opcode execution.
# Pulls the instruction at pc and args, and executes (increments sp)

    def execbyte(self, pc):
        pc, bytecode = self._next_byte(pc)
        #self.op_trace.append(hex(bytecode))

    # JR n
        if bytecode == 0x70:
            pc, jump = self._next_byte(pc)

            return pc + _sign_byte(jump)

    # %% Load Instructions (LD)
    # These instructions move data to, from, and between registers.
    # r,r': standard one-byte registers, i.e. (hl),a,c,b,e,d,l,h
    # rr: standard two-byte registers, i.e. bc,de,hl,sp
    # n,mn: signifies that an arg is required for this op; one byte or two, repectively.
    # (nr): refers to the set of mem locations (mn),(bc), and (de)
    # ar: refers to a and hl, the most-used registers.
    #
    # Flags:
    # Does not affect flags at all.

    # LD r, r'
        if bytecode & 0x88 == 8:
            src = (bytecode & 0x07)+4
            dest = ((bytecode & 0x70) >> 4)+4
            if src != dest:
                if src != 4:
                    val = self._get_byte_register(src)
                else:
                    val = self._get_hl_mem()
                    if self._fault_pending:
                        return pc
                if dest != 4:
                    self._set_byte_register(dest, val)
                else:
                    self._set_hl_mem(val)
                return pc
    # LD r, n
        if bytecode & 0x8F == 0x07:
            pc, val = self._next_byte(pc)
            if self._fault_pending:
                return pc
            dest = ((bytecode & 0x70) >> 4)+4
            if dest != 4:
                self._set_byte_register(dest, val)
            else:
                self._set_hl_mem(val)
            return pc

    # LD rr, mn
        if bytecode & 0xCF == 0x06:
            pc, val = self._next_short(pc)
            if self._fault_pending:
                return pc
            dest = ((bytecode & 0x30) >> 4)+3
            self._set_register(dest, val)
            return pc

    # LD (nr), ar
        if bytecode & 0xCF == 0x05:
            opid = (bytecode & 0x30) >> 4
            if opid == 0:
                val = self._get_register(self._HL_INDEX)
            else:
                val = self._get_byte_register(self._ACC_INDEX)
            if opid & 2 == 0:
                pc, dest = self._next_short(pc)
                if self._fault_pending:
                    return pc
                if opid == 0:
                    self._mem.write2(dest, val)
                else:
                    self._mem.write(dest, val)
            else:
                dest = self._get_register(3+(opid & 1))
                self._mem.write(dest, val)
            return pc

    # LD ar, (nr)
        if bytecode & 0xCF == 0x04:
            opid = (bytecode & 0x30) >> 4
            if opid & 2 == 0:
                pc, src = self._next_short(pc)
                if self._fault_pending:
                    return pc
                if opid == 0:
                    val = self._mem.read2(src)
                else:
                    val = self._mem.read(src)
            else:
                src = self._get_register(3+(opid & 1))
                val = self._mem.read(src)
            if self._fault_pending:
                return pc
            if opid == 0:
                self._set_register(self._HL_INDEX, val)
            else:
                self._set_byte_register(self._ACC_INDEX, val)
            return pc
    # LD (hl), br
        if bytecode & 0xFD == 0xF0:
            opid = (bytecode & 0x02) >> 1
            reg = opid + 3
            val = self._get_register(reg)
            self._set_hl_mem2(val)
            return pc
    # LD br, (hl)
        if bytecode & 0xFD == 0xF1:
            opid = (bytecode & 0x02) >> 1
            reg = opid + 3
            val = self._get_hl_mem2()
            if self._fault_pending:
                return pc
            self._set_register(reg, val)
            return pc

    # %% Exchange Instructions (EX)
    # These instructions exchange two registers (or hl and the top of the stack, (sp))
    # EX hl, rr is not reached if rr would be hl, as it is caught by the EX hl, (sp) check

    # EX hl, (sp)
        if bytecode == 0x23:
            sp = self._get_register(self._sp_index)
            val = self._mem.read2(sp)
            if self._fault_pending:
                return pc
            hl = self._get_register(self._HL_INDEX)
            self._mem.write2(sp, hl)
            if self._fault_pending:
                return pc
            self._set_register(self._HL_INDEX, val)
            return pc
    # EX hl, rr
        if bytecode & 0xCF == 0x03:
            reg = ((bytecode & 0x30) >> 4)+3
            val = self._get_register(reg)
            hl = self._get_register(self._HL_INDEX)
            self._set_register(reg, hl)
            self._set_register(self._HL_INDEX, val)
            return pc

    # %% I/O instructions (OUT, IN, TSTIO, OTRZ, INRZ, OTIR, INIR)
    # These instructions are fast ways to read/write from ports

    # OUT (), a
        if bytecode & 0xFE == 0xD0:
            if bytecode == 0xD0:
                # OUT (c) a
                dest = self._get_byte_register(self._port_reg_index)
            else:
                # OUT (n) a
                pc, dest = self._next_byte(pc)
                if self._fault_pending:
                    return pc+1
            val = self._get_byte_register(self._ACC_INDEX)
            dest |= 0xFF00
            self._mem.write(dest, val)
            return pc

    # OUT (n), n
        if bytecode == 0xD2:
            pc, val = self._next_byte(pc)
            if self._fault_pending:
                return pc
            pc, dest = self._next_byte(pc)
            if self._fault_pending:
                return pc
            dest |= 0xFF00
            self._mem.write(dest, val)
            return pc

    # IN
        if bytecode & 0xFE == 0xE0:
            if bytecode == 0xE0:
                # IN a, (c)
                dest = self._get_byte_register(self._port_reg_index)
            else:
                # IN a, (n)
                pc, dest = self._next_byte(pc)
                if self._fault_pending:
                    return pc+1
            dest |= 0xFF00
            val = self._mem.read(dest)
            if self._fault_pending:
                return pc
            self._set_byte_register(self._ACC_INDEX, val)
            return pc

    # TSTIO
        if bytecode & 0xFE == 0xC0:
            pc, tst = self._next_byte(pc)
            if self._fault_pending:
                return pc
            if bytecode == 0xC0:
                # TSTIO (c) n
                dest = self._get_byte_register(self._port_reg_index)
            else:
                # TSTIO (n) n
                pc, dest = self._next_byte(pc)
                if self._fault_pending:
                    return pc+1

            dest |= 0xFF00
            val = self._mem.read(dest)
            if self._fault_pending:
                return pc
            val &= tst

            self._update_flag(self.zero_mask, val == 0)
            return pc

    # OTRZ
        if bytecode == 0x40:
            hl = self._get_register(self._HL_INDEX)
            counter = self._get_byte_register(self._counter_index)
            port = self._get_byte_register(self._port_reg_index)

            val = self._get_hl_mem()
            if self._fault_pending:
                return pc
            if val != 0:
                self._mem.write(0xFF00 | port, val)
                if self._fault_pending:
                    return pc

            self._set_register(self._HL_INDEX, hl + 1)
            self._set_byte_register(self._counter_index, counter - 1)

            if counter-1 == 0 or val == 0:
                return pc
            return pc - 1
    # INRZ
        if bytecode == 0x41:
            hl = self._get_register(self._HL_INDEX)
            counter = self._get_byte_register(self._counter_index)
            port = self._get_byte_register(self._port_reg_index)

            val = self._mem.read(0xFF00 | port)
            if self._fault_pending:
                return pc

            self._set_hl_mem(val)
            if self._fault_pending:
                return pc

            self._set_register(self._HL_INDEX, hl + 1)
            self._set_byte_register(self._counter_index, counter - 1)
            if counter-1 == 0 or val == 0:
                return pc
            return pc - 1

    # OTIR
        if bytecode == 0xC2:
            hl = self._get_register(self._HL_INDEX)
            counter = self._get_byte_register(self._counter_index)
            port = self._get_byte_register(self._port_reg_index)

            val = self._get_hl_mem()
            if self._fault_pending:
                return pc

            self._mem.write(0xFF00 | port, val)
            if self._fault_pending:
                return pc

            self._set_register(self._HL_INDEX, hl + 1)
            self._set_byte_register(self._counter_index, counter - 1)

            if counter-1 == 0:
                return pc
            return pc - 1
    # INIR
        if bytecode == 0xC3:
            hl = self._get_register(self._HL_INDEX)
            counter = self._get_byte_register(self._counter_index)
            port = self._get_byte_register(self._port_reg_index)

            val = self._mem.read(0xFF00 | port)
            if self._fault_pending:
                return pc

            self._set_hl_mem(val)
            if self._fault_pending:
                return pc

            self._set_register(self._HL_INDEX, hl + 1)
            self._set_byte_register(self._counter_index, counter - 1)

            if counter-1 == 0:
                return pc
            return pc - 1

    # %% Data Copy instructions (LDI, LDD, LDIR, LDDR, SCAS)
    # These instructions copy large chunks of data.
    # Or for SCAS, merely scan the data

    # LD.
        if bytecode & 0xFE == 0x20:
            hl = self._get_register(self._HL_INDEX)
            bc = self._get_register(3)
            de = self._get_register(4)

            val = self._mem.read(hl)
            if self._fault_pending:
                return pc

            self._mem.write(de, val)
            if self._fault_pending:
                return pc

            if bytecode & 0x1 == 0:
                hl -= 1
                de -= 1
            else:
                hl += 1
                de += 1
            self._set_register(self._HL_INDEX, hl)
            self._set_register(4, de)
            self._set_register(3, bc - 1)

            return pc

    # LD.R
        if bytecode & 0xFE == 0x30:
            hl = self._get_register(self._HL_INDEX)
            bc = self._get_register(3)
            de = self._get_register(4)

            val = self._mem.read(hl)
            if self._fault_pending:
                return pc

            self._mem.write(de, val)
            if self._fault_pending:
                return pc

            if bytecode & 0x1 == 0:
                hl -= 1
                de -= 1
            else:
                hl += 1
                de += 1
            self._set_register(self._HL_INDEX, hl)
            self._set_register(4, de)
            self._set_register(3, bc - 1)

            if bc-1 == 0:
                return pc
            return pc - 1

    # SCAS
        if bytecode == 0x01:
            hl = self._get_register(self._HL_INDEX)
            bc = self._get_register(3)
            a = self._get_byte_register(self._ACC_INDEX)

            val = self._get_hl_mem()
            if self._fault_pending:
                return pc

            self._set_register(self._HL_INDEX, hl + 1)
            self._set_register(3, bc - 1)

            self._update_flag(self.zero_mask, val == a)

            if bc-1 == 0 or val == 0 or val == a:
                return pc
            return pc - 1

    # %% Decrement and Increment Instructions (DEC,INC)
    # These instructions increment/decrement a given register.
    # Flags:
    #   Carry bit reset; set if bit 8 is removed during adding; i.e. 0x00-0x01=0xFF, with a carry.
    #   Overflow bit reset; set if adding two negative nums and getting a positive, or vice versa.
    #   Zero bit reset; set if result is 0

    # DEC r
        if bytecode & 0x8F == 0x84:
            reg = ((bytecode & 0x70) >> 4)+4
            if reg != 4:
                oldval = self._get_byte_register(reg)
            else:
                oldval = self._get_hl_mem()
                if self._fault_pending:
                    return pc

            val = (oldval - 1) & 0xFF

            self._update_flag(self.zero_mask, val == 0)

            if reg != 4:
                self._set_byte_register(reg, val)
            else:
                self._set_hl_mem(val)
            return pc
    # INC r
        if bytecode & 0x8F == 0x85:
            reg = ((bytecode & 0x70) >> 4)+4
            if reg != 4:
                oldval = self._get_byte_register(reg)
            else:
                oldval = self._get_hl_mem()
                if self._fault_pending:
                    return pc

            val = (oldval + 1) & 0xFF

            self._update_flag(self.zero_mask, val == 0)

            if reg != 4:
                self._set_byte_register(reg, val)
            else:
                self._set_hl_mem(val)
            return pc

    # DEC rr
        if bytecode & 0xCF == 0x44:
            reg = ((bytecode & 0x30) >> 4)+3
            oldval = self._get_register(reg)

            val = (oldval - 1) & 0xFFFF

            self._update_flag(self.zero_mask, val == 0)

            self._set_register(reg, val)
            return pc

    # INC rr
        if bytecode & 0xCF == 0x45:
            reg = ((bytecode & 0x30) >> 4)+3
            oldval = self._get_register(reg)

            val = (oldval + 1) & 0xFFFF

            self._update_flag(self.zero_mask, val == 0)

            self._set_register(reg, val)
            return pc

    # %% Basic Math Instructions (ADD,SUB,ADC,SBC,MUL,CP, NEG, SCF, CCF)
    # These use either hl or a as the main register in question.
    # Note that the carry flag is determined by whether the value is smaller than the old value (when adding),
    #   or larger than the old value (when subtracting). The comparisons use the unsigned byte form (0<=b<256)

    # ADD a, r
        if bytecode & 0xF8 == 0x88:
            src = (bytecode & 0x07)+4
            if src != 4:
                val = self._get_byte_register(src)
            else:
                val = self._get_hl_mem()
                if self._fault_pending:
                    return pc

            oldval = self._get_byte_register(self._ACC_INDEX)
            val = oldval + val

            self._update_flag(self.zero_mask, val & 0xFF == 0)
            self._update_flag(self.carry_mask, val > 0xFF)

            self._set_byte_register(self._ACC_INDEX, val)
            return pc

    # SUB a, r
        if bytecode & 0xF8 == 0x98:
            src = (bytecode & 0x07)+4
            if src != 4:
                val = self._get_byte_register(src)
            else:
                val = self._get_hl_mem()
                if self._fault_pending:
                    return pc

            oldval = self._get_byte_register(self._ACC_INDEX)
            val = oldval - val

            self._update_flag(self.zero_mask, val & 0xFF == 0)
            self._update_flag(self.carry_mask, val < 0)

            self._set_byte_register(self._ACC_INDEX, val)
            return pc

    # ADC a, r
        if bytecode & 0xF8 == 0xA8:
            src = (bytecode & 0x07)+4
            if src != 4:
                val = self._get_byte_register(src)
            else:
                val = self._get_hl_mem()
                if self._fault_pending:
                    return pc

            val += self._get_flag(self.carry_mask)

            oldval = self._get_byte_register(self._ACC_INDEX)
            val = oldval + val

            self._update_flag(self.zero_mask, val & 0xFF == 0)
            self._update_flag(self.carry_mask, val > 0xFF)

            self._set_byte_register(self._ACC_INDEX, val)
            return pc

    # SBC a, r
        if bytecode & 0xF8 == 0xB8:
            src = (bytecode & 0x07)+4
            if src != 4:
                val = self._get_byte_register(src)
            else:
                val = self._get_hl_mem()
                if self._fault_pending:
                    return pc

            val += self._get_flag(self.carry_mask)

            oldval = self._get_byte_register(self._ACC_INDEX)
            val = oldval - val

            self._update_flag(self.zero_mask, val & 0xFF == 0)
            self._update_flag(self.carry_mask, val < 0)

            self._set_byte_register(self._ACC_INDEX, val)
            return pc

    # AND a, r
        if bytecode & 0xF8 == 0xC8:
            src = (bytecode & 0x07)+4
            if src != 4:
                val = self._get_byte_register(src)
            else:
                val = self._get_hl_mem()
                if self._fault_pending:
                    return pc

            oldval = self._get_byte_register(self._ACC_INDEX)
            val = oldval & val

            self._update_flag(self.zero_mask, val == 0)
            self._update_flag(self.carry_mask, False)

            self._set_byte_register(self._ACC_INDEX, val)
            return pc

    # OR a, r
        if bytecode & 0xF8 == 0xD8:
            src = (bytecode & 0x07)+4
            if src != 4:
                val = self._get_byte_register(src)
            else:
                val = self._get_hl_mem()
                if self._fault_pending:
                    return pc

            oldval = self._get_byte_register(self._ACC_INDEX)
            val = oldval | val

            self._update_flag(self.zero_mask, val == 0)
            self._update_flag(self.carry_mask, False)

            self._set_byte_register(self._ACC_INDEX, val)
            return pc

    # XOR a, r
        if bytecode & 0xF8 == 0xE8:
            src = (bytecode & 0x07)+4
            if src != 4:
                val = self._get_byte_register(src)
            else:
                val = self._get_hl_mem()
                if self._fault_pending:
                    return pc

            oldval = self._get_byte_register(self._ACC_INDEX)
            val = oldval ^ val

            self._update_flag(self.zero_mask, val == 0)
            self._update_flag(self.carry_mask, False)

            self._set_byte_register(self._ACC_INDEX, val)
            return pc

    # CP a, r
        if bytecode & 0xF8 == 0xF8:
            src = (bytecode & 0x07)+4
            if src != 4:
                val = self._get_byte_register(src)
            else:
                val = self._get_hl_mem()
                if self._fault_pending:
                    return pc

            oldval = self._get_byte_register(self._ACC_INDEX)
            val = oldval - val

            self._update_flag(self.zero_mask, val & 0xFF == 0)
            self._update_flag(self.carry_mask, val < 0)

            return pc

    # ADD a, n
        if bytecode == 0x87:
            pc, val = self._next_byte(pc)
            if self._fault_pending:
                return pc

            oldval = self._get_byte_register(self._ACC_INDEX)
            val = oldval + val

            self._update_flag(self.zero_mask, val & 0xFF == 0)
            self._update_flag(self.carry_mask, val > 0xFF)

            self._set_byte_register(self._ACC_INDEX, val)
            return pc

    # SUB a, n
        if bytecode == 0x97:
            pc, val = self._next_byte(pc)
            if self._fault_pending:
                return pc

            oldval = self._get_byte_register(self._ACC_INDEX)
            val = oldval - val

            self._update_flag(self.zero_mask, val & 0xFF == 0)
            self._update_flag(self.carry_mask, val < 0)

            self._set_byte_register(self._ACC_INDEX, val)
            return pc

    # ADC a, n
        if bytecode == 0xA7:
            pc, val = self._next_byte(pc)
            if self._fault_pending:
                return pc

            val += self._get_flag(self.carry_mask)

            oldval = self._get_byte_register(self._ACC_INDEX)
            val = oldval + val

            self._update_flag(self.zero_mask, val & 0xFF == 0)
            self._update_flag(self.carry_mask, val > 0xFF)

            self._set_byte_register(self._ACC_INDEX, val)
            return pc

    # SBC a, n
        if bytecode == 0xB7:
            pc, val = self._next_byte(pc)
            if self._fault_pending:
                return pc

            val += self._get_flag(self.carry_mask)

            oldval = self._get_byte_register(self._ACC_INDEX)
            val = oldval - val

            self._update_flag(self.zero_mask, val & 0xFF == 0)
            self._update_flag(self.carry_mask, val < 0)

            self._set_byte_register(self._ACC_INDEX, val)
            return pc

    # AND a, n
        if bytecode == 0xC7:
            pc, val = self._next_byte(pc)
            if self._fault_pending:
                return pc

            oldval = self._get_byte_register(self._ACC_INDEX)
            val = oldval & val

            self._update_flag(self.zero_mask, val == 0)
            self._update_flag(self.carry_mask, False)

            self._set_byte_register(self._ACC_INDEX, val)
            return pc

    # OR a, n
        if bytecode == 0xD7:
            pc, val = self._next_byte(pc)
            if self._fault_pending:
                return pc

            oldval = self._get_byte_register(self._ACC_INDEX)
            val = oldval | val

            self._update_flag(self.zero_mask, val == 0)
            self._update_flag(self.carry_mask, False)

            self._set_byte_register(self._ACC_INDEX, val)
            return pc

    # XOR a, n
        if bytecode == 0xE7:
            pc, val = self._next_byte(pc)
            if self._fault_pending:
                return pc

            oldval = self._get_byte_register(self._ACC_INDEX)
            val = oldval ^ val

            self._update_flag(self.zero_mask, val == 0)
            self._update_flag(self.carry_mask, False)

            self._set_byte_register(self._ACC_INDEX, val)
            return pc

    # CP a, n
        if bytecode == 0xF7:
            pc, val = self._next_byte(pc)
            if self._fault_pending:
                return pc

            oldval = self._get_byte_register(self._ACC_INDEX)

            val = oldval - val

            self._update_flag(self.zero_mask, val & 0xFF == 0)
            self._update_flag(self.carry_mask, val < 0)

            return pc

    # TST a, n
        if bytecode == 0xF6:
            pc, val = self._next_byte(pc)
            if self._fault_pending:
                return pc

            oldval = self._get_byte_register(self._ACC_INDEX)

            val = oldval & val

            self._update_flag(self.zero_mask, val & 0xFF == 0)

            return pc

    # ADC hl, rr
        if bytecode & 0xCF == 0x46:
            reg = ((bytecode & 0x30) >> 4)+3
            val = self._get_register(reg)

            val += self._get_flag(self.carry_mask)

            oldval = self._get_register(self._HL_INDEX)

            val = oldval + val

            self._update_flag(self.zero_mask, val & 0xFFFF == 0)
            self._update_flag(self.carry_mask, val > 0xFFFF)

            self._set_register(self._HL_INDEX, val)
            return pc

    # SBC hl, rr
        if bytecode & 0xCF == 0x86:
            reg = ((bytecode & 0x30) >> 4)+3
            val = self._get_register(reg)

            val += self._get_flag(self.carry_mask)

            oldval = self._get_register(self._HL_INDEX)

            val = oldval - val

            self._update_flag(self.zero_mask, val & 0xFFFF == 0)
            self._update_flag(self.carry_mask, val < 0)

            self._set_register(self._HL_INDEX, val)
            return pc

    # RLA
        if bytecode == 0xC6:
            oldval = self._get_byte_register(self._ACC_INDEX)

            val = oldval << 1
            val += self._get_flag(self.carry_mask)
            val &= 0xFF

            self._update_flag(self.zero_mask, val == 0)
            self._update_flag(self.carry_mask, oldval & 0x80)

            self._set_byte_register(self._ACC_INDEX, val)
            return pc

    # RRA
        if bytecode == 0xD6:
            oldval = self._get_byte_register(self._ACC_INDEX)

            val = oldval >> 1
            if self._get_flag(self.carry_mask):
                val |= 0x80

            self._update_flag(self.zero_mask, val == 0)
            self._update_flag(self.carry_mask, oldval & 0x01)

            self._set_byte_register(self._ACC_INDEX, val)
            return pc

    # MLT hl
        if bytecode == 0x12:
            val = self._get_register(self._HL_INDEX)
            lval = val & 0x00FF
            hval = (val & 0xFF00) >> 8
            nval = hval*lval
            self._set_register(self._HL_INDEX, nval)
            return pc

    # NEG
        if bytecode == 0xE6:
            val = self._get_register(self._ACC_INDEX)
            val = -val
            self._set_register(self._ACC_INDEX, val)
            return pc

    # SCF
        if bytecode == 0x22:
            self._update_flag(self.carry_mask, True)
            return pc

    # CCF
        if bytecode == 0x32:
            carry = self._get_flag(self.carry_mask)
            self._update_flag(self.carry_mask, carry == 0)
            return pc

    # %% Control Flow Instructions (DJNZ, JP, JR, CALL, RET)
    # These instructions are used to control the flow of a program, by changing the program counter.
    #

    # DJNZ
        if bytecode == 0x43:
            pc, jump = self._next_byte(pc)
            if self._fault_pending:
                return pc

            oldval = self._get_byte_register(self._counter_index)

            val = (oldval - 1) & 0xFF

            self._set_byte_register(self._counter_index, val)

            if val != 0:
                return pc + _sign_byte(jump)
            return pc
    # JP hl
        if bytecode == 0x42:
            return self._get_register(self._HL_INDEX)

    # JR condition n
        if bytecode & 0xCF == 0x80:
            pc, jump = self._next_byte(pc)

            if self._flag_condition_met((bytecode >> 4) & 0x3):
                return pc + _sign_byte(jump)
            return pc
    # JP mn
        if bytecode == 0x71:
            pc, jump = self._next_short(pc)

            return jump
    # JP condition mn
        if bytecode & 0xCF == 0x81:
            pc, jump = self._next_short(pc)

            if self._flag_condition_met((bytecode >> 4) & 0x3):
                return jump
            return pc
    # CALL mn
        if bytecode == 0x72:
            pc, jump = self._next_short(pc)
            self._push(pc)
            return jump
    # CALL condition mn
        if bytecode & 0xCF == 0x82:
            pc, jump = self._next_short(pc)
            if self._flag_condition_met((bytecode >> 4) & 0x3):
                self._push(pc)
                return jump
            return pc
    # RET
        if bytecode == 0x73:
            return self._pop()
    # RET condition
        if bytecode & 0xCF == 0x83:
            if self._flag_condition_met((bytecode >> 4) & 0x3):
                return self._pop()
            return pc
    # %% Stack instructions (PUSH, POP, STKLIM)

    # PUSH pr
        if bytecode & 0xFC == 0x50:
            reg = (bytecode & 0x03) + 2
            val = self._get_register(reg)
            self._push(val)
            return pc
    # POP pr
        if bytecode & 0xFC == 0x60:
            reg = (bytecode & 0x03) + 2
            val = self._pop()
            if self._fault_pending:
                return pc
            self._set_register(reg, val)
            return pc

    # STKLIM
        if bytecode == 0x02:
            val = self._get_register(self._HL_INDEX)
            self._set_sp_min(val)
            return pc

    # %% Interrupt Instructions (TRAP, RETI, HALT, EI, DI)

    # TRAP
        if bytecode == 0xE2:
            pc, val = self._next_byte(pc)
            pc = self._syscall(pc, val)
            return pc

    # RETI
        if bytecode == 0xE3:
            if not self.kernel_mode():
                self.fault(ILLOP, URETI)
                return pc
            pc = self._reti()
            return pc

    # HALT
        if bytecode == 0xD3:
            if self._level < 2 or not self.interrupts_enabled:
                self.fault(ILLOP, INFHALT)
                return pc
            if self._level > 2:
                self.fault(ILLOP, USRHALT)
                return pc
            self.halted = True
            return pc

    # EI
        if bytecode == 0x10:
            if not self.kernel_mode():
                self.fault(ILLOP, UEI)
                return pc
            self.interrupts_enabled = True
            return pc

    # DI
        if bytecode == 0x11:
            if not self.kernel_mode():
                self.fault(ILLOP, UDI)
                return pc
            self.interrupts_enabled = False
            return pc

    # %% NOP
        if bytecode == 0:
            return pc

    # %% End of opcode resolution (unknown)
        self.fault(ILLOP)   # Unknown
        return pc

# %% Helper methods and stuff

    def _get_flag(self, flag_mask):
        return int(self.byteregisters[self._flag_index] & flag_mask)

    def _update_flag(self, flag_mask, set_flag):
        if set_flag:
            self.byteregisters[self._flag_index] |= flag_mask
        else:
            self.byteregisters[self._flag_index] &= (~flag_mask) & 0xFF

    # Conveniently, 0 is 'falsy' and any other int is 'truthy'
    def _flag_condition_met(self, condition):
        match (condition):
            case 0: return self._get_flag(self.zero_mask)
            case 1: return self._get_flag(self.carry_mask)
            case 2: return not self._get_flag(self.zero_mask)
            case 3: return not self._get_flag(self.carry_mask)

    def _push(self, val):
        sp = self._get_sp() - 2
        if sp < self._get_sp_min():
            self.fault(STACK_OVERFLOW, STACK_PUSH)
            return
        self._mem.write2(sp, val)
        if not self._fault_pending:
            self._set_sp(sp)

    def _pop(self):
        sp = self._get_sp()
        if sp < self._get_sp_min():
            self.fault(STACK_OVERFLOW, STACK_POP)
        val = self._mem.read2(sp)
        if not self._fault_pending:
            self._set_sp(sp+2)
        return val

    def _next_byte(self, pc):
        return pc+1, self._mem.read(pc)

    def _next_short(self, pc):
        return pc+2, self._mem.read2(pc)

    def set_pc(self, val):
        self._set_register(0, val)

    def _set_sp_min(self, val):
        self._set_register(1, val)

    def _set_flags(self, val):
        self._set_byte_register(self._flag_index, val)

    def _set_sp(self, val):
        self._set_register(self._sp_index, val)

    def _get_pc(self):
        return self._get_register(0)

    def _get_sp_min(self):
        return self._get_register(1)

    def _get_flags(self):
        return self._get_byte_register(self._flag_index)

    def _get_sp(self):
        return self._get_register(self._sp_index)

    def _get_hl_mem(self):
        return self._mem.read(self._get_register(self._HL_INDEX))

    def _set_hl_mem(self, val):
        self._mem.write(self._get_register(self._HL_INDEX), val)

    def _get_hl_mem2(self):
        return self._mem.read2(self._get_register(self._HL_INDEX))

    def _set_hl_mem2(self, val):
        self._mem.write2(self._get_register(self._HL_INDEX), val)

    def _set_register(self, reg, val):
        self.registers[reg] = val & 0xFFFF

    def _set_byte_register(self, reg, val):
        self.byteregisters[reg] = val & 0xFF

    def _get_register(self, reg):
        return int(self.registers[reg])

    def _get_byte_register(self, reg):
        return int(self.byteregisters[reg])


def _sign_byte(byte):
    byte &= 0xFF
    if byte > 0x7F:
        return byte - 0x100
    return byte

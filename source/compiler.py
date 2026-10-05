
from source.utils import (get_sys_path, get_assembly_path, resolve_expr,
                            tokenize_line, expand_labels)


class Compiler:

    def __init__(self):
        self.vars = {}
        self.pendinglocs = []
        self.headerlocs = []
        self.offset = 0
        self.last_global_label = ""

        self.data = bytearray()
        self.header = bytearray()
        self.parent_files = set()
        self.included_files = set()

        self.byteregisters = ["(hl)", "a", "c", "b", "e", "d", "l", "h"]
        self.shortregisters = ["bc", "de", "hl", "sp"]
        self.stackregisters = ["af", "bc", "de", "hl"]
        self.jumpconditions = ["z", "c", "nz", "nc"]

    def compile_assembly(self, filename):
        self.vars.clear()
        self.headerlocs.clear()
        self.pendinglocs.clear()
        self.offset = 0
        self.last_global_label = ""
        self.header.clear()
        self.data.clear()
        self.parent_files.clear()
        self.included_files.clear()
        self._compile_include(filename)

    def _compile_include(self, filename):
        if filename in self.parent_files:
            raise ValueError("Circular include detected!")
        self.parent_files.add(filename)
        if filename in self.included_files:
            return
        self.included_files.add(filename)

        filepath = get_assembly_path(filename)

        try:
            with open(filepath, "r", encoding="ASCII") as src:
                for line in src:
                    # Remove comments from the line, split into cmd and args.
                    clean_line = line.split(";", 1)[0].strip()
                    if len(clean_line) == 0:
                        # Ignore it, it's a blank line or just a comment
                        continue
                    args = tokenize_line(clean_line)
                    if len(args) == 0:
                        continue
                    match (args[0].upper()):
                        case ".DEF": self._op_def(args)
                        case ".SCOPE": self._op_scope(args)
                        case ".ORG": self._op_org(args)
                        case ".HEADER": self._op_header(args)
                        case ".DS": self._op_ds(args)
                        case ".FILL": self._op_fill(args)
                        case ".ALIGN": self._op_align(args)
                        case ".LBL": self._op_lbl(args)
                        case ".STR": self._op_str(args)
                        case ".TXT": self._op_txt(args)
                        case ".BYTES": self._op_bytes(args)
                        case ".SHORTS": self._op_shorts(args)
                        case ".BYTE": self._op_byte(args)
                        case ".SHORT": self._op_short(args)
                        case ".INC": self._op_inc(args)
    
                        case "STOP": self._macro_stop(args)
    
                        case "NOP": self._cmd_nop(args)
    
                        case "LD": self._cmd_ld(args)
                        case "EX": self._cmd_ex(args)
    
                        case "LDIR": self._cmd_ldir(args)
                        case "LDDR": self._cmd_lddr(args)
                        case "LDI": self._cmd_ldi(args)
                        case "LDD": self._cmd_ldd(args)
    
                        case "OUT": self._cmd_out(args)
                        case "IN": self._cmd_in(args)
                        case "TSTIO": self._cmd_tst_io(args)
    
                        case "OTIR": self._cmd_otir(args)
                        case "INIR": self._cmd_inir(args)
                        case "OTRZ": self._cmd_otrz(args)
                        case "INRZ": self._cmd_inrz(args)
    
                        case "INC": self._cmd_inc(args)
                        case "DEC": self._cmd_dec(args)
    
                        case "ADD": self._cmd_add(args)
                        case "SUB": self._cmd_sub(args)
                        case "ADC": self._cmd_adc(args)
                        case "SBC": self._cmd_sbc(args)
    
                        case "AND": self._cmd_and(args)
                        case "OR": self._cmd_or(args)
                        case "XOR": self._cmd_xor(args)
                        case "CP": self._cmd_cp(args)
                        case "TST": self._cmd_tst(args)
    
                        case "RLA": self._cmd_rla(args)
                        case "RRA": self._cmd_rra(args)
    
                        case "MLT": self._cmd_mlt(args)
    
                        case "SCAS": self._cmd_scas(args)
                        case "SCF": self._cmd_scf(args)
                        case "CCF": self._cmd_ccf(args)
                        case "NEG": self._cmd_neg(args)
    
                        case "STKLIM": self._cmd_stklim(args)
                        case "PUSH": self._cmd_push(args)
                        case "POP": self._cmd_pop(args)
    
                        case "DJNZ": self._cmd_djnz(args)
                        case "JR": self._cmd_jr(args)
                        case "JP": self._cmd_jp(args)
                        case "CALL": self._cmd_call(args)
                        case "RET": self._cmd_ret(args)
    
                        case "RETI": self._cmd_reti(args)
                        case "TRAP": self._cmd_trap(args)
                        case "HALT": self._cmd_halt(args)
                        case "EI": self._cmd_ei(args)
                        case "DI": self._cmd_di(args)
    
                        case _: self._raise_invalid_err(args)
        except IOError:
            raise ValueError(f"File {filename} at {filepath} not found")
        self.parent_files.remove(filename)
        return self.offset

    def populate_assembly(self):
        for loc in self.pendinglocs:
            offset, size, expr = loc
            val = resolve_expr(expr, self.vars)
            if size == -1:
                distance = val-offset-1
                if distance < -128 or distance > 127:
                    raise ValueError(
                        f"Location {expr} is too far away ({distance})! Distance must be between -128 and 127."
                    )
                self.data[offset] = distance & 0xFF
            elif size == 1:
                self.data[offset] = val & 0xFF
            elif size == 2:
                self.data[offset] = val & 0xFF
                self.data[offset + 1] = (val >> 8) & 0xFF

        for loc in self.headerlocs:
            offset, size, expr = loc
            val = resolve_expr(expr, self.vars)
            if size == 1:
                self.header[offset] = val & 0xFF
            elif size == 2:
                self.header[offset] = val & 0xFF
                self.header[offset + 1] = (val >> 8) & 0xFF

    def compile_full(self, filein, fileout):
        self.compile_assembly(filein)
        self.populate_assembly()
        self.save_assembly(fileout)

    def save_assembly(self, filename):
        filepath = get_sys_path(filename)
        with open(filepath, "wb") as dest:
            dest.write(self.header)
            dest.write(self.data)

    def _parse_num(self, arg):
        base = 10
        if "0x" in arg:
            base = 16
        if "0b" in arg:
            base = 2
        return int(arg, base)

    def _parse_val(self, arg, size):
        try:
            return self._parse_num(arg)
        except ValueError as ve:
            arg = expand_labels(self.last_global_label, arg)
            self.pendinglocs.append((self.offset, size, arg))
            return 0

    # Short helpers for convenience
    def _validate_varname(self, var):
        if var.startswith('.'):
            var = self.last_global_label + '_' + var[1:]
        elif var.isidentifier():
            self.last_global_label = var
        if not var.isidentifier():
            raise ValueError(
                f"'{var}' is an invalid variable name"
            )
        if var in self.vars:
            raise ValueError(
                f"'{var}' already defined as {hex(self.vars[var])}"
            )
        return var

    def _raise_invalid_err(self, args):
        argstr = ' '.join(args)
        raise ValueError(
            f"'{argstr}' is not a valid instruction"
        )

    def _check_args(self, args, expected):
        if len(args)-1 != expected:
            raise ValueError(
                f"'{args[0]}' op needs {expected} args, {len(args)-1} given"
            )

    def _write_byte(self, byte):
        byte &= 0xFF
        gap_len = self.offset - len(self.data)
        if gap_len < 0:
            self.data[self.offset] = byte
        elif gap_len == 0:
            self.data.append(byte)
        else:
            self.data.extend([0] * gap_len)
            self.data.append(byte)
        self.offset += 1

    def _write_short(self, short):
        self._write_byte(short)
        self._write_byte(short >> 8)

    def _write_block(self, block):
        slice_len = min(len(self.data) - self.offset, len(block))
        gap_len = self.offset - len(self.data)
        add_len = len(block) - slice_len
        if gap_len > 0:
            self.data.extend([0] * gap_len)
        if slice_len > 0:
            self.data[self.offset:self.offset+slice_len] = block[:slice_len]
        if add_len > 0:
            self.data.extend(block[slice_len:])
        self.offset += len(block)

    def _is_indirection(self, arg):
        return arg.startswith("(") and arg.endswith(")")

# %% Compiler Commands
# Commands that do not compile directly into bytecode, but are instead used internally in the compiler
# These commands are utilities making it possible to load strings or other data into memory,
# as well as making it far easier to use CALL/JP instructions via label vars.

    def _op_def(self, args):
        self._check_args(args, 2)
        var = self._validate_varname(args[1])
        val = resolve_expr(args[2], self.vars, self.last_global_label)
        self.vars[var] = val

    def _op_scope(self, args):
        self._check_args(args, 1)
        var = args[1]
        if var.isidentifier():
            self.last_global_label = var
        else:
            raise ValueError(
                f"'{var}' is an invalid scope name"
            )

    def _op_lbl(self, args):
        self._check_args(args, 1)
        var = self._validate_varname(args[1])
        self.vars[var] = self.offset

    def _op_inc(self, args):
        self._check_args(args, 1)
        self._compile_include(args[1])

    def _op_org(self, args):
        self._check_args(args, 1)
        val = resolve_expr(args[1], self.vars, self.last_global_label)
        self.offset = val

    def _op_header(self, args):
        self._check_args(args, 0)
        self.offset = 0
        self.header.clear()
        self.headerlocs.clear()

        self.header.extend(self.data)
        self.headerlocs.extend(self.pendinglocs)

        self.data.clear()
        self.pendinglocs.clear()

    def _op_str(self, args):
        self._op_txt(args)
        self._write_byte(0x00)

    def _op_txt(self, args):
        if len(args) == 3:
            var = self._validate_varname(args[1])
            self.vars[var] = self.offset
        else:
            self._check_args(args, 1)

        valstr = args[-1]

        fchar = valstr[0]
        if fchar in ("'", '"'):
            if fchar == valstr[-1]:
                str_data = self.process_string_escapes(valstr[1:-1])
                self._write_block(str_data)
            else:
                raise ValueError(
                    f"End quote not found in string data '{valstr}'"
                )
        else:
            raise ValueError(
                f"Start quote not found in string data '{valstr}'"
            )

    def _op_fill(self, args):
        if len(args) == 4:
            var = self._validate_varname(args[1])
            self.vars[var] = self.offset
        else:
            self._check_args(args, 2)

        size = resolve_expr(args[-2], self.vars, self.last_global_label) & 0xFFFF
        val = resolve_expr(args[-1], self.vars, self.last_global_label) & 0xFF

        self._write_block([val] * size)

    def _op_ds(self, args):
        if len(args) == 3:
            var = self._validate_varname(args[1])
            self.vars[var] = self.offset
        else:
            self._check_args(args, 1)

        size = resolve_expr(args[-1], self.vars, self.last_global_label) & 0xFFFF

        self._write_block([0] * size)

    def _op_align(self, args):
        if len(args) == 3:
            var = self._validate_varname(args[1])
            self.vars[var] = self.offset
        else:
            self._check_args(args, 1)

        size = resolve_expr(args[-1], self.vars, self.last_global_label) & 0xFFFF

        offset = self.offset % size
        if offset != 0:
            padding = size - offset
            self._write_block([0] * padding)

    def _op_byte(self, args):
        if len(args) == 3:
            var = self._validate_varname(args[1])
            self.vars[var] = self.offset
        else:
            self._check_args(args, 1)

        val = self._parse_val(args[-1], 1)
        self._write_byte(val & 0xFF)

    def _op_bytes(self, args):
        if len(args) == 1:
            self._check_args(args, 1)

        for arg in args[1:]:
            val = self._parse_val(arg, 1)
            self._write_byte(val & 0xFF)

    def _op_short(self, args):
        if len(args) == 3:
            var = self._validate_varname(args[1])
            self.vars[var] = self.offset
        else:
            self._check_args(args, 1)

        val = self._parse_val(args[-1], 2)
        self._write_short(val & 0xFFFF)

    def _op_shorts(self, args):
        if len(args) == 1:
            self._check_args(args, 1)

        for arg in args[1:]:
            val = self._parse_val(arg, 2)
            self._write_short(val & 0xFFFF)

    def process_string_escapes(self, raw_str):
        # Standard ASCII/ANSI escapes
        escapes = {
            "\\n": "\n",   # Line Feed (10)
            "\\r": "\r",   # Carriage Return (13)
            "\\t": "\t",   # Tab (9)
            "\\b": "\b",   # Backspace (8)
            "\\e": "\x1b", # Escape (27) - Essential for colors!
            "\\0": "\0"    # Null (0)
            }

        for key, value in escapes.items():
            raw_str = raw_str.replace(key, value)

        # Convert the resulting string into a list of integers
        return [ord(c) for c in raw_str]
# %% STOP macro
# Stops execution
# Writes to the appropriate system port

    def _macro_stop(self, args):
        self._check_args(args, 0)
        self._write_byte(0xD2)
        self._write_byte(0xFF)
        self._write_byte(0x00)

# %% NOP command
# Literally does nothing; 'no operation'

    def _cmd_nop(self, args):
        self._check_args(args, 0)
        self._write_byte(0x00)

# %% LD command
# Valid first args: hl, a, bc, de, sp, b, c, d, e, h, l, (bc), (de), (hl), (#), (*)
# Valid second args are dependent on the first arg.

    def _cmd_ld(self, args):
        self._check_args(args, 2)
        arg1 = args[1].lower()
        arg2 = args[2].lower()
        if arg1 == arg2:
            self._raise_invalid_err(args)

        if arg1 in self.byteregisters:
            upper = self.byteregisters.index(arg1) << 4
            if arg2 in self.byteregisters:
                # LD r, r'
                lower = 8 + self.byteregisters.index(arg2)
                self._write_byte(upper+lower)
                return
            if arg1 == "a" and self._is_indirection(arg2):
                # LD a, (nr)
                arg2 = arg2[1:-1]
                match arg2:
                    case "bc":
                        self._write_byte(0x24)
                    case "de":
                        self._write_byte(0x34)
                    case _:
                        self._write_byte(0x14)
                        num = self._parse_val(arg2, 2)
                        self._write_short(num)
                return
            if arg2 == 'bc':
                # LD (hl), bc
                self._write_byte(0xF0)
                return
            if arg2 == 'de':
                # LD (hl), de
                self._write_byte(0xF2)
                return
            # LD r, n
            self._write_byte(upper+7)
            num = self._parse_val(arg2, 1)
            self._write_byte(num)
            return

        if arg1 in self.shortregisters:
            if self._is_indirection(arg2):
                arg2 = arg2[1:-1]
                match arg1:
                    case "hl":
                        # LD hl, (mn)
                        self._write_byte(0x04)
                        num = self._parse_val(arg2, 2)
                        self._write_short(num)
                        return
                    case "bc":
                        if arg2 != "hl":
                            self._raise_invalid_err(args)
                        # LD bc, (hl)
                        self._write_byte(0xF1)
                        return
                    case "de":
                        if arg2 != "hl":
                            self._raise_invalid_err(args)
                        # LD de, (hl)
                        self._write_byte(0xF3)
                        return
                    case _:
                        self._raise_invalid_err(args)
            # LD rr, mn
            upper = self.shortregisters.index(arg1) << 4
            self._write_byte(upper + 0x6)
            num = self._parse_val(arg2, 2)
            self._write_short(num)
            return

        if self._is_indirection(arg1):
            arg1 = arg1[1:-1]
            match arg2:
                case "hl":
                    # LD (mn), hl
                    self._write_byte(0x05)
                    num = self._parse_val(arg1, 2)
                    self._write_short(num)
                case "a":
                    # LD (nr), a
                    match arg1:
                        case "bc":
                            self._write_byte(0x25)
                        case "de":
                            self._write_byte(0x35)
                        case _:
                            self._write_byte(0x15)
                            num = self._parse_val(arg1, 2)
                            self._write_short(num)
                case _:
                    self._raise_invalid_err(args)
            return
        # Whatever it is, it's not valid if it reaches this point
        self._raise_invalid_err(args)

# %% EX command
# Valid first arg: hl
# Valid second args: rr, except hl, and (sp)
    def _cmd_ex(self, args):
        self._check_args(args, 2)
        if args[1] == "hl":
            match (args[2]):
                case "bc": self._write_byte(0x03)
                case "de": self._write_byte(0x13)
                case "(sp)": self._write_byte(0x23)
                case "sp": self._write_byte(0x33)
                case _: self._raise_invalid_err(args)
            return
        # Whatever it is, it's not valid if it reaches this point
        self._raise_invalid_err(args)


# %% LDDR command
    def _cmd_lddr(self, args):
        self._check_args(args, 0)
        self._write_byte(0x30)

# %% LDIR command
    def _cmd_ldir(self, args):
        self._check_args(args, 0)
        self._write_byte(0x31)

# %% LDD command
    def _cmd_ldd(self, args):
        self._check_args(args, 0)
        self._write_byte(0x20)

# %% LDI command
    def _cmd_ldi(self, args):
        self._check_args(args, 0)
        self._write_byte(0x21)

# %% OUT command
    def _cmd_out(self, args):
        self._check_args(args, 2)
        port = args[1]
        if not self._is_indirection(port):
            self._raise_invalid_err(args)
        port = port[1:-1]

        if args[2] == "a":
            if port == 'c':
                self._write_byte(0xD0)
                return
            self._write_byte(0xD1)
        else:
            self._write_byte(0xD2)
            val = self._parse_val(args[2], 1)
            self._write_byte(val)
        port = self._parse_val(port, 1)
        self._write_byte(port)

# %% IN command
    def _cmd_in(self, args):
        self._check_args(args, 2)
        port = args[2]
        if not self._is_indirection(port):
            self._raise_invalid_err(args)
        if not args[1] == "a":
            self._raise_invalid_err(args)
        port = port[1:-1]
        if port == 'c':
            self._write_byte(0xE0)
            return
        self._write_byte(0xE1)
        val = self._parse_val(port, 1)
        self._write_byte(val)

# %% TSTIO command
    def _cmd_tst_io(self, args):
        self._check_args(args, 2)
        port = args[1]
        if not self._is_indirection(port):
            self._raise_invalid_err(args)
        port = port[1:-1]
        if port == "c":
            self._write_byte(0xC0)
            val = self._parse_val(args[2], 1)
            self._write_byte(val)
        else:
            self._write_byte(0xC1)
            val = self._parse_val(args[2], 1)
            self._write_byte(val)
            port = self._parse_val(port, 1)
            self._write_byte(port)

# %% OTIR command
    def _cmd_otir(self, args):
        self._check_args(args, 0)
        self._write_byte(0xC2)

# %% INIR command
    def _cmd_inir(self, args):
        self._check_args(args, 0)
        self._write_byte(0xC3)

# %% OTRZ command
    def _cmd_otrz(self, args):
        self._check_args(args, 0)
        self._write_byte(0x40)

# %% INRZ command
    def _cmd_inrz(self, args):
        self._check_args(args, 0)
        self._write_byte(0x41)

# %% INC command
# Valid first args: any rr, r, including (hl)
# Valid second args are dependent on the first arg.
    def _cmd_inc(self, args):
        self._check_args(args, 1)
        arg = args[1].lower()
        if arg in self.byteregisters:
            # INC r
            upper = self.byteregisters.index(arg) << 4
            self._write_byte(upper + 0x85)
            return
        if arg in self.shortregisters:
            # INC rr
            upper = self.shortregisters.index(arg) << 4
            self._write_byte(upper + 0x45)
            return
        # Whatever it is, it's not valid if it reaches this point
        self._raise_invalid_err(args)
# %% DEC command
# Valid first args: any rr, r, including (hl)
# Valid second args are dependent on the first arg.

    def _cmd_dec(self, args):
        self._check_args(args, 1)
        arg = args[1].lower()
        if arg in self.byteregisters:
            # DEC r
            upper = self.byteregisters.index(arg) << 4
            self._write_byte(upper + 0x84)
            return
        if arg in self.shortregisters:
            # DEC r
            upper = self.shortregisters.index(arg) << 4
            self._write_byte(upper + 0x44)
            return
        # Whatever it is, it's not valid if it reaches this point
        self._raise_invalid_err(args)
# %% ADD command
# Valid first args: a
# Valid second args: any r or n

    def _cmd_add(self, args):
        self._check_args(args, 2)
        arg = args[2].lower()
        if args[1] == "a":
            if arg in self.byteregisters:
                # ADD a, r
                lower = self.byteregisters.index(arg)
                self._write_byte(0x88 + lower)
                return
            # ADD a, n
            self._write_byte(0x87)
            num = self._parse_val(arg, 1)
            self._write_byte(num)
            return

        # Whatever it is, it's not valid if it reaches this point
        self._raise_invalid_err(args)
# %% SUB command
# Valid first args: a
# Valid second args: any r or n

    def _cmd_sub(self, args):
        self._check_args(args, 2)
        arg = args[2].lower()
        if args[1] == "a":
            if arg in self.byteregisters:
                # SUB a, r
                lower = self.byteregisters.index(arg)
                self._write_byte(0x98 + lower)
                return

            # SUB a, n
            self._write_byte(0x97)
            num = self._parse_val(arg, 1)
            self._write_byte(num)
            return

        # Whatever it is, it's not valid if it reaches this point
        self._raise_invalid_err(args)
# %% ADC command
# Valid first args: a, hl
# Valid second args: any r/n or rr, respectively
# Valid second args are dependent on the first arg.

    def _cmd_adc(self, args):
        self._check_args(args, 2)
        arg = args[2].lower()
        if args[1] == "a":
            if arg in self.byteregisters:
                # ADC a, r
                lower = self.byteregisters.index(arg)
                self._write_byte(0xA8 + lower)
                return

            # ADC a, n
            self._write_byte(0xA7)
            num = self._parse_val(arg, 1)
            self._write_byte(num)
            return
        if args[1] == "hl":
            # ADC hl, rr
            if arg in self.shortregisters:
                upper = self.shortregisters.index(arg) << 4
                self._write_byte(upper + 0x46)
                return

        # Whatever it is, it's not valid if it reaches this point
        self._raise_invalid_err(args)
# %% SBC command
# Valid first args: a, hl
# Valid second args: any r/n or rr, respectively
# Valid second args are dependent on the first arg.

    def _cmd_sbc(self, args):
        self._check_args(args, 2)
        arg = args[2].lower()
        if args[1] == "a":
            if arg in self.byteregisters:
                # SBC a, r
                lower = self.byteregisters.index(arg)
                self._write_byte(0xB8 + lower)
                return

            # SBC a, n
            self._write_byte(0xB7)
            num = self._parse_val(arg, 1)
            self._write_byte(num)
            return
        if args[1] == "hl":
            # SBC hl, rr
            if arg in self.shortregisters:
                upper = self.shortregisters.index(arg) << 4
                self._write_byte(upper + 0x86)
                return

        # Whatever it is, it's not valid if it reaches this point
        self._raise_invalid_err(args)
# %% AND command
# Valid first args: a
# Valid second args: any r or n

    def _cmd_and(self, args):
        self._check_args(args, 2)
        arg = args[2].lower()
        if args[1] == "a":
            if arg in self.byteregisters:
                # ADD a, r
                lower = self.byteregisters.index(arg)
                self._write_byte(0xC8 + lower)
                return
            # ADD a, n
            self._write_byte(0xC7)
            num = self._parse_val(arg, 1)
            self._write_byte(num)
            return

        # Whatever it is, it's not valid if it reaches this point
        self._raise_invalid_err(args)
# %% OR command
# Valid first args: a
# Valid second args: any r or n

    def _cmd_or(self, args):
        self._check_args(args, 2)
        arg = args[2].lower()
        if args[1] == "a":
            if arg in self.byteregisters:
                # ADD a, r
                lower = self.byteregisters.index(arg)
                self._write_byte(0xD8 + lower)
                return
            # ADD a, n
            self._write_byte(0xD7)
            num = self._parse_val(arg, 1)
            self._write_byte(num)
            return

        # Whatever it is, it's not valid if it reaches this point
        self._raise_invalid_err(args)
# %% XOR command
# Valid first args: a
# Valid second args: any r or n

    def _cmd_xor(self, args):
        self._check_args(args, 2)
        arg = args[2].lower()
        if args[1] == "a":
            if arg in self.byteregisters:
                # ADD a, r
                lower = self.byteregisters.index(arg)
                self._write_byte(0xE8 + lower)
                return
            # ADD a, n
            self._write_byte(0xE7)
            num = self._parse_val(arg, 1)
            self._write_byte(num)
            return

        # Whatever it is, it's not valid if it reaches this point
        self._raise_invalid_err(args)
# %% CP command
# Valid first args: a
# Valid second args: any r or n

    def _cmd_cp(self, args):
        self._check_args(args, 2)
        arg = args[2].lower()
        if args[1] == "a":
            if arg in self.byteregisters:
                # CP a, r
                lower = self.byteregisters.index(arg)
                self._write_byte(0xF8 + lower)
                return
            # CP a, n
            self._write_byte(0xF7)
            num = self._parse_val(arg, 1)
            self._write_byte(num)
            return

        # Whatever it is, it's not valid if it reaches this point
        self._raise_invalid_err(args)

# %% TST command
# Valid first args: a
# Valid second args: any r or n

    def _cmd_tst(self, args):
        self._check_args(args, 2)
        arg = args[2].lower()
        if args[1] == "a":
            # TST a, n
            self._write_byte(0xF6)
            num = self._parse_val(arg, 1)
            self._write_byte(num)
            return

        # Whatever it is, it's not valid if it reaches this point
        self._raise_invalid_err(args)

# %% RLA command
# No args: one RLA
# One arg: macro, add n RLA instructs

    def _cmd_rla(self, args):
        if len(args) == 2:
            try:
                num = self._parse_num(args[1])
            except ValueError:
                self._raise_invalid_err(args)
            for i in range(num):
                self._write_byte(0xC6)
            return
        self._check_args(args, 0)
        self._write_byte(0xC6)

# %% RRA command
# No args: one RRA
# One arg: macro, add n RRA instructs

    def _cmd_rra(self, args):
        if len(args) == 2:
            try:
                num = self._parse_num(args[1])
            except ValueError:
                self._raise_invalid_err(args)
            for i in range(num):
                self._write_byte(0xD6)
            return
        self._check_args(args, 0)
        self._write_byte(0xD6)

# %% MLT command
# Only one valid form: MLT hl

    def _cmd_mlt(self, args):
        self._check_args(args, 1)
        if args[1] == "hl":
            self._write_byte(0x12)
            return
        # Whatever it is, it's not valid if it reaches this point
        self._raise_invalid_err(args)

# %% SCAS command
    def _cmd_scas(self, args):
        self._check_args(args, 0)
        self._write_byte(0x01)

# %% SCF command
    def _cmd_scf(self, args):
        self._check_args(args, 0)
        self._write_byte(0x22)

# %% CCF command
    def _cmd_ccf(self, args):
        self._check_args(args, 0)
        self._write_byte(0x32)

# %% NEG command
    def _cmd_neg(self, args):
        self._check_args(args, 0)
        self._write_byte(0xE6)

# %% STKLIM command
# No args

    def _cmd_stklim(self, args):
        self._check_args(args, 0)
        self._write_byte(0x02)

# %% PUSH command
# Valid args: any pr (af, bc, de, hl)

    def _cmd_push(self, args):
        self._check_args(args, 1)
        arg = args[1].lower()
        if arg in self.stackregisters:
            # PUSH pr
            lower = self.stackregisters.index(arg)
            self._write_byte(0x50 + lower)
            return
        # Whatever it is, it's not valid if it reaches this point
        self._raise_invalid_err(args)
# %% POP command
# Valid args: any pr (af, bc, de, hl)

    def _cmd_pop(self, args):
        self._check_args(args, 1)
        arg = args[1].lower()
        if arg in self.stackregisters:
            # POP pr
            lower = self.stackregisters.index(arg)
            self._write_byte(0x60 + lower)
            return
        # Whatever it is, it's not valid if it reaches this point
        self._raise_invalid_err(args)
# %% DJNZ command
# One arg: Relative jump distance.
# Numeric literal -> taken as relative
# Compiler variable -> taken as absolute (translated to relative)

    def _cmd_djnz(self, args):
        self._check_args(args, 1)
        arg = args[1].lower()
        self._write_byte(0x43)
        num = self._parse_val(arg, -1)
        self._write_byte(num)
# %% JR command
# One arg: Relative jump distance.
# Or two, counting conditionals (i.e. JR Z n)
# Numeric literal -> taken as relative
# Compiler variable -> taken as absolute (translated to relative)

    def _cmd_jr(self, args):
        if len(args) == 3:
            # JR condition n
            condition = args[1].lower()
            if condition not in self.jumpconditions:
                self._raise_invalid_err(args)
                return

            upper = self.jumpconditions.index(condition) << 4

            self._write_byte(0x80 + upper)
            arg = args[2].lower()
            num = self._parse_val(arg, -1)
            self._write_byte(num)
        else:
            # JR n
            self._check_args(args, 1)
            arg = args[1].lower()
            self._write_byte(0x70)
            num = self._parse_val(arg, -1)
            self._write_byte(num)
# %% JP command
# One arg: Jump location
# Or two, counting conditionals (i.e. JP Z mn)

    def _cmd_jp(self, args):
        if len(args) == 3:
            # JP condition mn
            condition = args[1].lower()
            if condition not in self.jumpconditions:
                self._raise_invalid_err(args)
                return

            upper = self.jumpconditions.index(condition) << 4
            self._write_byte(0x81 + upper)
            arg = args[2].lower()
            num = self._parse_val(arg, 2)
            self._write_short(num)
        else:
            self._check_args(args, 1)
            arg = args[1].lower()
            if arg == "hl":
                # JP hl
                self._write_byte(0x42)
            else:
                # JP mn
                self._write_byte(0x71)
                num = self._parse_val(arg, 2)
                self._write_short(num)
# %% CALL command
# One arg: Jump location
# Or two, counting conditionals (i.e. CALL Z mn)

    def _cmd_call(self, args):
        if len(args) == 3:
            # CALL condition mn
            condition = args[1].lower()
            if condition not in self.jumpconditions:
                self._raise_invalid_err(args)
                return

            upper = self.jumpconditions.index(condition) << 4
            self._write_byte(0x82 + upper)
            arg = args[2].lower()
            num = self._parse_val(arg, 2)
            self._write_short(num)
        else:
            # CALL mn
            self._check_args(args, 1)
            arg = args[1].lower()
            self._write_byte(0x72)
            num = self._parse_val(arg, 2)
            self._write_short(num)
# %% RET command
# No args
# Or one, counting conditionals (i.e. RET Z)

    def _cmd_ret(self, args):
        if len(args) == 2:
            # RET condition
            condition = args[1].lower()
            if condition not in self.jumpconditions:
                self._raise_invalid_err(args)
                return

            upper = self.jumpconditions.index(condition) << 4
            self._write_byte(0x83 + upper)
        else:
            # RET
            self._check_args(args, 0)
            self._write_byte(0x73)

# %% RETI command
# No args

    def _cmd_reti(self, args):
        self._check_args(args, 0)
        self._write_byte(0xE3)
# %% TRAP command
# One arg: syscall id

    def _cmd_trap(self, args):
        self._check_args(args, 1)
        self._write_byte(0xE2)
        val = self._parse_val(args[1], 1)
        self._write_byte(val)
# %% HALT command
# No args

    def _cmd_halt(self, args):
        self._check_args(args, 0)
        self._write_byte(0xD3)
# %% EI command
# No args

    def _cmd_ei(self, args):
        self._check_args(args, 0)
        self._write_byte(0x10)
# %% DI command
# No args

    def _cmd_di(self, args):
        self._check_args(args, 0)
        self._write_byte(0x11)

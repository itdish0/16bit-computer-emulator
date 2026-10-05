
import re
import os
import os.path as osp
import fnmatch

BASE_DIR = osp.dirname(osp.dirname(osp.abspath(__file__)))


def get_sys_path(filename):
    return osp.join(BASE_DIR, filename)


SAFE_DIR = get_sys_path("Computer")


def get_safe_path(filename):
    return osp.join(SAFE_DIR, filename)


ASSEMBLY_DIR = get_sys_path("Assembly")


def get_assembly_path(filename):
    return osp.join(ASSEMBLY_DIR, filename)


def sanitize_path(sandbox, filename):
    abs_sandbox = osp.abspath(sandbox)
    target = osp.abspath(osp.join(sandbox, filename))

    if (osp.commonpath([abs_sandbox, target]) == abs_sandbox
            and target != abs_sandbox):
        # Must be a file in the sandbox, not the sandbox itself
        return target
    else:
        return ''


def find_files(parent_dir, pattern):
    all_files = os.listdir(parent_dir)
    return fnmatch.filter(all_files, pattern)


def tokenize_line(line):
    # This finds commands, quoted strings, and math expressions
    # while respecting commas as separators.
    pattern = r'[a-zA-Z.]+|(?:"[^"]*"|[^,])+'
    tokens = re.findall(pattern, line)

    return [t.strip() for t in tokens]


def resolve_expr(expr, labels, last_global=None):
    expr = expand_labels(last_global, expr)
    try:
        # We make eval handle both string replacement and the math
        val = int(eval(expr, {"__builtins__": {}}, labels))
    except ZeroDivisionError as e:
        raise ValueError(
            f"Math Error: Division by zero in expression '{expr}'"
        ) from e
    except NameError as e:
        # This happens if a label wasn't found in your dictionary
        raise ValueError(
            f"Symbol Error: Unknown label in expression '{expr}'"
        ) from e
    except Exception as e:
        raise ValueError(
            f"General Math Error: '{expr}' is invalid ({e})"
        ) from e

    return val


def expand_labels(last_global, expr):
    # 1. Expand local aliases (e.g. '.loop' -> 'main_loop')
    if last_global:
        expr = re.sub(
            r'(?<![a-zA-Z0-9_])\.([a-zA-Z_][a-zA-Z0-9_]*)',
            last_global + r'_\1', expr
        )

    # 2. Convert explicit global calls (e.g. 'main.loop' -> 'main_loop')
    expr = re.sub(
        r'([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)',
        r'\1_\2', expr
    )
    return expr

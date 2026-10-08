# src/main.py

import math
import sys
import operator
import re
import os

# ==============================================================================
# 1. 数据结构定义
# ==============================================================================
class Symbol(str):
    """表示 Scheme 中的符号"""
    pass

class StringLiteral(str):
    """表示 Scheme 中的字符串字面量"""
    pass

class Nil:
    """表示空表 ()"""
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    def __repr__(self): return '()'
    def __eq__(self, other): return isinstance(other, Nil) or other == []

class Procedure:
    """表示 Scheme 中的闭包"""
    def __init__(self, params, body, env):
        self.params = params
        self.body = body
        self.env = env

    def __call__(self, *args):
        new_env = Environment(outer=self.env)
        for i, p in enumerate(self.params):
            if i < len(args):
                new_env[p] = args[i]
        result = None
        for expr in self.body:
            result = Evaluator.eval(expr, new_env)
        return result

# ==============================================================================
# 2. 词法分析器 (Tokenizer)
# ==============================================================================
class Tokenizer:
    def __init__(self, text):
        self.tokens = []
        self._tokenize(text)

    def _tokenize(self, text):
        lines = text.split('\n')
        lines = [line.split(';')[0] for line in lines]
        text = ' '.join(lines)
        self.tokens = re.findall(r"'|\(|\)|\"(?:\\.|[^\"\\])*\"|[^\s()']+", text)

# ==============================================================================
# 3. 语法分析器 (Parser)
# ==============================================================================
class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def parse(self):
        if self.pos >= len(self.tokens): return None
        token = self.tokens[self.pos]
        
        if token == "'":
            self.pos += 1
            return ['quote', self.parse()]
            
        self.pos += 1
        
        if token == '(':
            lst = []
            while self.pos < len(self.tokens) and self.tokens[self.pos] != ')':
                lst.append(self.parse())
            if self.pos >= len(self.tokens):
                raise SyntaxError("缺少右括号 ')'")
            self.pos += 1
            return lst
        elif token == ')':
            raise SyntaxError("意外的 ')'")
        else:
            return self._atom(token)

    def _atom(self, token):
        if token == '#t' or token.lower() == 'true': return True
        elif token == '#f' or token.lower() == 'false': return False
        elif token.startswith('"') and token.endswith('"'):
            return StringLiteral(token[1:-1].replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"'))
        try: return int(token)
        except ValueError:
            try: return float(token)
            except ValueError: return Symbol(token)

# ==============================================================================
# 4. 环境 (Environment)
# ==============================================================================
class Environment(dict):
    def __init__(self, params=(), args=(), outer=None):
        super().__init__()
        self.outer = outer
        if isinstance(params, (list, tuple)):
            for p, a in zip(params, args):
                self[p] = a

    def find(self, var):
        if var in self: return self
        elif self.outer is not None: return self.outer.find(var)
        else: raise NameError(f"未定义的变量: {var}")

# ==============================================================================
# 5. 内置过程 (Standard Library)
# ==============================================================================
def scheme_car(x):
    if isinstance(x, list) and len(x) > 0: return x[0]
    if isinstance(x, tuple) and len(x) == 2: return x[0]
    if isinstance(x, Nil): return Nil()
    return Nil()

def scheme_cdr(x):
    if isinstance(x, list):
        if len(x) <= 1: return Nil()
        return x[1:]
    if isinstance(x, tuple) and len(x) == 2: return x[1]
    if isinstance(x, Nil): return Nil()
    return Nil()

def scheme_cons(x, y):
    if isinstance(y, list): return [x] + y
    if isinstance(y, Nil): return [x]
    return (x, y)

def scheme_list(*args):
    return list(args)

def standard_env():
    env = Environment()
    
    def scheme_eq(x, y):
        if isinstance(x, (int, float)) and not isinstance(x, bool) and isinstance(y, (int, float)) and not isinstance(y, bool):
            return x == y
        if type(x) != type(y): return False
        if isinstance(x, (bool, Symbol, StringLiteral)): return x == y
        if isinstance(x, Nil): return True
        return x is y

    def scheme_equal(x, y):
        if isinstance(x, (int, float)) and not isinstance(x, bool) and isinstance(y, (int, float)) and not isinstance(y, bool):
            return x == y
        if type(x) != type(y): return False
        if isinstance(x, (bool, Symbol, StringLiteral)): return x == y
        if isinstance(x, Nil): return True
        if isinstance(x, list):
            if len(x) != len(y): return False
            return all(scheme_equal(x[i], y[i]) for i in range(len(x)))
        if isinstance(x, tuple):
            return scheme_equal(x[0], y[0]) and scheme_equal(x[1], y[1])
        return x is y

    def scheme_cmp(op, *args):
        for i in range(len(args)-1):
            a, b = args[i], args[i+1]
            
            # 1. 布尔值与非布尔值绝对不相等，布尔值之间只允许 =
            if isinstance(a, bool) != isinstance(b, bool):
                return False
            if isinstance(a, bool) and isinstance(b, bool):
                if op != '=' or a != b: return False
                continue
            
            # 2. 数字与数字比较（允许 int 和 float 混合，如 (= 1 1.0) -> #t）
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                if op == '=' and a != b: return False
                if op == '<' and not (a < b): return False
                if op == '>' and not (a > b): return False
                if op == '<=' and not (a <= b): return False
                if op == '>=' and not (a >= b): return False
                continue

            # 3. 符号与符号比较（按字典序）
            if isinstance(a, Symbol) and isinstance(b, Symbol):
                if op == '=' and a != b: return False
                if op == '<' and not (a < b): return False
                if op == '>' and not (a > b): return False
                if op == '<=' and not (a <= b): return False
                if op == '>=' and not (a >= b): return False
                continue
                
            # 4. 其他任何类型组合（如数字与符号、符号与字符串），直接返回 False
            return False
        return True

    def scheme_display(x):
        sys.stdout.write(format_scheme_display(x))
        return None

    def scheme_newline():
        sys.stdout.write('\n')
        return None

    env.update({
        '+': lambda *args: sum(args),
        '-': lambda *args: -args[0] if len(args) == 1 else args[0] - sum(args[1:]),
        '*': lambda *args: math.prod(args) if hasattr(math, 'prod') else __import__('functools').reduce(operator.mul, args, 1),
        '/': lambda *args: 1 / args[0] if len(args) == 1 else int(args[0] / (math.prod(args[1:]) if hasattr(math, 'prod') else __import__('functools').reduce(operator.mul, args[1:], 1))),
        'modulo': lambda x, y: x % y,
        'quotient': lambda x, y: int(x / y),
        'expt': pow,
        'abs': abs, 'min': min, 'max': max,
        '=': lambda *args: scheme_cmp('=', *args),
        '<': lambda *args: scheme_cmp('<', *args),
        '>': lambda *args: scheme_cmp('>', *args),
        '<=': lambda *args: scheme_cmp('<=', *args),
        '>=': lambda *args: scheme_cmp('>=', *args),
        'cons': scheme_cons,
        'car': scheme_car,
        'cdr': scheme_cdr,
        'list': scheme_list,
        'length': lambda x: len(x) if isinstance(x, list) else 0,
        'append': lambda x, y: x + y if isinstance(x, list) and isinstance(y, list) else y,
        'null?': lambda x: isinstance(x, Nil) or x == [],
        'pair?': lambda x: isinstance(x, tuple) or (isinstance(x, list) and len(x) > 0),
        'list?': lambda x: isinstance(x, list) or isinstance(x, Nil),
        'number?': lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
        'boolean?': lambda x: isinstance(x, bool),
        'symbol?': lambda x: isinstance(x, Symbol),
        'string?': lambda x: isinstance(x, StringLiteral),
        'procedure?': lambda x: isinstance(x, (Procedure, type(lambda: 0))),
        'zero?': lambda x: x == 0,
        'even?': lambda x: x % 2 == 0,
        'odd?': lambda x: x % 2 != 0,
        'eq?': scheme_eq,
        'equal?': scheme_equal,
        'not': lambda x: x is False,
        'display': scheme_display,
        'newline': scheme_newline,
    })
    return env

# ==============================================================================
# 6. 求值器 (Evaluator)
# ==============================================================================
class Evaluator:
    @staticmethod
    def eval(x, env):
        if isinstance(x, StringLiteral): return x
        if isinstance(x, Symbol): return env.find(x)[x]
        elif not isinstance(x, list): return x
        if len(x) == 0: return Nil()
        
        op = x[0]
        if op == 'quote':
            return Evaluator._convert_quote(x[1])
        elif op == 'if':
            test, conseq = x[1], x[2]
            alt = x[3] if len(x) > 3 else None
            # 严格判断，只有 #f 是假
            return Evaluator.eval(conseq if Evaluator.eval(test, env) is not False else alt, env)
        elif op == 'cond':
            for clause in x[1:]:
                if len(clause) > 0:
                    test = clause[0]
                    if test == 'else' or Evaluator.eval(test, env) is not False:
                        result = None
                        for expr in clause[1:]:
                            result = Evaluator.eval(expr, env)
                        return result
            return None
        elif op == 'define':
            target = x[1]
            body = x[2:]
            if isinstance(target, list):
                env[target[0]] = Procedure(target[1:], body, env)
                return target[0]
            else:
                env[target] = Evaluator.eval(body[0], env)
                return target
        elif op == 'lambda':
            return Procedure(x[1], x[2:], env)
        elif op == 'begin':
            result = None
            for expr in x[1:]:
                result = Evaluator.eval(expr, env)
            return result
        elif op == 'let':
            bindings = x[1]
            body = x[2:]
            new_env = Environment(outer=env)
            evaluated = [(b[0], Evaluator.eval(b[1], env)) for b in bindings]
            for var, val in evaluated:
                new_env[var] = val
            result = None
            for expr in body:
                result = Evaluator.eval(expr, new_env)
            return result
        elif op == 'and':
            result = True
            for expr in x[1:]:
                result = Evaluator.eval(expr, env)
                if result is False: return False
            return result
        elif op == 'or':
            for expr in x[1:]:
                result = Evaluator.eval(expr, env)
                if result is not False: return result
            return False

        proc = Evaluator.eval(op, env)
        args = [Evaluator.eval(arg, env) for arg in x[1:]]
        if callable(proc):
            return proc(*args)
        else:
            raise TypeError(f"不可调用的对象: {proc}")

    @staticmethod
    def _convert_quote(data):
        if isinstance(data, (Symbol, StringLiteral, int, float, bool)): return data
        if isinstance(data, list):
            if len(data) == 3 and data[1] == '.':
                return (Evaluator._convert_quote(data[0]), Evaluator._convert_quote(data[2]))
            return [Evaluator._convert_quote(x) for x in data]
        return data

# ==============================================================================
# 7. 输出格式化
# ==============================================================================
def format_output(val):
    if val is True: return '#t'
    if val is False: return '#f'
    if isinstance(val, Nil): return '()'
    if isinstance(val, tuple) and len(val) == 2:
        return '(' + format_output(val[0]) + ' . ' + format_output(val[1]) + ')'
    if isinstance(val, list):
        if len(val) == 0: return '()'
        return '(' + ' '.join(format_output(x) for x in val) + ')'
    if isinstance(val, StringLiteral):
        s = str(val).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\t', '\\t')
        return f'"{s}"'
    if isinstance(val, Symbol): return str(val)
    if callable(val): return '#<procedure>'
    if isinstance(val, float) and val.is_integer(): return str(int(val))
    return str(val)

def format_scheme_display(val):
    if val is True: return '#t'
    if val is False: return '#f'
    if isinstance(val, Nil): return '()'
    if isinstance(val, tuple) and len(val) == 2:
        return '(' + format_scheme_display(val[0]) + ' . ' + format_scheme_display(val[1]) + ')'
    if isinstance(val, list):
        if len(val) == 0: return '()'
        return '(' + ' '.join(format_scheme_display(x) for x in val) + ')'
    if isinstance(val, StringLiteral): return str(val)
    if isinstance(val, Symbol): return str(val)
    if callable(val): return '#<procedure>'
    if isinstance(val, float) and val.is_integer(): return str(int(val))
    return str(val)

# ==============================================================================
# 8. 运行程序 (核心逻辑)
# ==============================================================================
def run_program(text, env):
    tokenizer = Tokenizer(text)
    parser = Parser(tokenizer.tokens)
    while True:
        try:
            expr = parser.parse()
            if expr is None: break
            result = Evaluator.eval(expr, env)
            if result is not None:
                sys.stdout.write(format_output(result) + '\n')
                sys.stdout.flush()
        except Exception as e:
            sys.stderr.write(f"Error: {e}\n")
            sys.stderr.flush()
            break

# ==============================================================================
# 9. 主程序入口
# ==============================================================================
def main():
    args = sys.argv[1:]
    env = standard_env()
    
    if args:
        program_text = ""
        for filename in args:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    program_text += f.read() + "\n"
            else:
                sys.stderr.write(f"错误：找不到文件 {filename}\n")
                sys.exit(1)
        run_program(program_text, env)
    elif sys.stdin.isatty():
        print("Mini-Scheme 解释器 (输入 exit 或 Ctrl+D 退出)")
        buffer = ""
        while True:
            try:
                prompt = ">>> " if not buffer else "... "
                line = input(prompt)
                if line.strip().lower() == 'exit': break
                buffer += line + "\n"
                if buffer.count('(') > buffer.count(')'): continue
                run_program(buffer, env)
                buffer = ""
            except Exception as e:
                print(f"错误: {e}")
                buffer = ""
    else:
        program_text = sys.stdin.read()
        run_program(program_text, env)

if __name__ == '__main__':
    main()

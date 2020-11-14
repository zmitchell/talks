import ast
import sys


class ASTGenerator:
    def __init__(self):
        self.asts = dict()
        self.filename = None
        self.block_types = [
            ast.If,
            ast.For,
            ast.While,
            ast.Try,
            ast.ExceptHandler,
            ast.With,
            ast.ClassDef,
            ast.FunctionDef,
            ast.AsyncFunctionDef,
            ast.AsyncFor,
            ast.AsyncWith,
        ]
        self.func_types = [ast.FunctionDef, ast.AsyncFunctionDef]

    def _parse_module(self):
        try:
            with open(self.filename, "r") as file:
                module_str = file.read()
        except IOError:
            sys.exit(f"Could not open file {self.filename}")
        module_str.replace("\r\n", "\n").replace("\r", "\n")
        if not module_str.endswith("\n"):
            module_str += "\n"
        return ast.parse(module_str, filename=self.filename)

    @staticmethod
    def _key_for_item(item):
        filename = getattr(item, "__file__", None)
        if filename is not None:
            filename.replace(".pyc", ".py")
            return filename, 0

        code_obj = item.__code__
        filename = code_obj.co_filename
        lineno = code_obj.co_firstlineno
        filename.replace(".pyc", ".py")
        return filename, lineno

    def _find_funcs(self, parent_ast):
        for item in parent_ast.body:
            if type(item) in self.func_types:
                self.asts[(self.filename, item.lineno)] = item
                self._find_funcs(item)
            elif type(item) in self.block_types:
                self._find_funcs(item)
            else:
                continue

    def __call__(self, item):
        item_key = self._key_for_item(item)  # (module filename, item's line number)
        self.filename = item_key[0]
        item_ast = self.asts.get(item_key)
        if item_ast is not None:
            return item_ast

        module_key = (self.filename, 0)
        module_ast = self._parse_module()
        self.asts[module_key] = module_ast
        self._find_funcs(module_ast)
        item_ast = self.asts.get(item_key)
        if item_ast is not None:
            return item_ast

        raise NameError(f"Function or method {item.__qualname__} not found")


class FieldBounds:
    def __init__(self):
        self.lower_bound = None
        self.upper_bound = None
        self.field_name = None
        self.left_op = None
        self.right_op = None


class InRangeFactory:
    def __init__(self, content, field_name, cls):
        self.module_ast = None
        self.field_name = field_name
        self.ast_gen = ASTGenerator()
        self.bounds = self._extract_bounds(content)
        self.macro_contents = content
        self.new_methods = []
        self.new_init_stmts = []
        self.cls = cls

    def __call__(self):
        self.invoke()

    @staticmethod
    def _extract_bounds(contents):
        bounds = FieldBounds()
        bounds.left_op = contents.args[0].ops[0]
        bounds.right_op = contents.args[0].ops[1]
        left_item = contents.args[0].left
        if isinstance(left_item, ast.Num):
            bounds.lower_bound = left_item.n
        elif isinstance(left_item, ast.UnaryOp):
            if isinstance(left_item.op, ast.USub):
                bounds.lower_bound = -1 * left_item.operand.n
            elif isinstance(left_item.op, ast.UAdd):
                bounds.lower_bound = left_item.operand.n
            else:
                # bound = astor.dump_tree(left_item)
                bound = "astor thing"
                raise ValueError(f"Invalid bound for 'inrange': {bound}")
        else:
            # bound = astor.dump_tree(left_item)
            bound = "astor thing"
            raise ValueError(f"Invalid bound for 'inrange': {bound}")
        right_item = contents.args[0].comparators[1]
        if isinstance(right_item, ast.Num):
            bounds.upper_bound = right_item.n
        elif isinstance(right_item, ast.UnaryOp):
            if isinstance(right_item.op, ast.USub):
                bounds.upper_bound = -1 * right_item.operand.n
            elif isinstance(right_item.op, ast.UAdd):
                bounds.upper_bound = right_item.operand.n
            else:
                # bound = astor.dump_tree(right_item)
                bound = "astor thing"
                raise ValueError(f"Invalid bound for 'inrange': {bound}")
        else:
            # bound = astor.dump_tree(right_item)
            bound = "astor thing"
            raise ValueError(f"Invalid bound for 'inrange': {bound}")
        return bounds

    def invoke(self):
        has_class_specific_init = self.cls.__init__.__qualname__.endswith(
            f"{self.cls.__name__}.__init__"
        )
        if has_class_specific_init:
            self._modify_init()
        else:
            self._add_init()
        setter_body = self._if_block()
        getter_func = self._getter()
        setter_func = self._setter(setter_body)
        setattr(self.cls, self.field_name, property(getter_func, setter_func))
        return self.cls

    def _add_init(self):
        attr = ast.Attribute(
            value=ast.Name(id="self", ctx=ast.Load()),
            attr=f"_{self.field_name}",
            ctx=ast.Store(),
        )
        var_init = ast.Assign(targets=[attr], value=ast.Name(id="None", ctx=ast.Load()))
        self_arg = ast.arg(arg="self", annotation=None)
        func_args = basic_func_args(self_arg)
        func_node = ast.FunctionDef(
            name="__init__",
            args=func_args,
            body=[var_init],
            decorator_list=[],
            returns=None,
        )
        mod_node = ast.Module(body=[func_node])
        init_func = ast_to_func(mod_node, "__init__")
        setattr(self.cls, "__init__", init_func.__get__(self.cls))

    def _modify_init(self):
        qualname = self.cls.__init__.__qualname__
        ast_gen = ASTGenerator()
        current_ast = ast_gen(self.cls.__init__)
        attr = ast.Attribute(
            value=ast.Name(id="self", ctx=ast.Load()),
            attr=f"_{self.field_name}",
            ctx=ast.Store(),
        )
        var_init = ast.Assign(targets=[attr], value=ast.Name(id="None", ctx=ast.Load()))
        current_ast.body.append(var_init)
        mod_node = ast.Module(body=[current_ast])
        init_func = ast_to_func(mod_node, "__init__")
        init_func.__qualname__ = qualname
        setattr(self.cls, "__init__", init_func.__get__(self.cls))

    def _if_block(self):
        new_value = ast.Name(id="new", ctx=ast.Load())  # the value passed to the setter
        inst_var = ast.Attribute(
            value=ast.Name(id="self", ctx=ast.Load()),
            attr=f"_{self.field_name}",
            ctx=ast.Store(),
        )
        lower_comp = ast.Compare(
            left=ast.Num(n=self.bounds.lower_bound),
            ops=[self.bounds.left_op],
            comparators=[new_value],
        )
        upper_comp = ast.Compare(
            left=new_value,
            ops=[self.bounds.right_op],
            comparators=[ast.Num(n=self.bounds.upper_bound)],
        )
        comps = [lower_comp, upper_comp]
        accept_condition = ast.BoolOp(op=ast.And(), values=comps)
        assign_stmt = ast.Assign(targets=[inst_var], value=new_value)
        except_msg = self._except_msg()
        range_exception = ast.Call(
            func=ast.Name(id="ValueError", ctx=ast.Load()),
            args=[ast.Str(s=except_msg)],
            keywords=[],
        )
        else_stmt = ast.Raise(exc=range_exception, cause=None)
        if_node = ast.If(test=accept_condition, body=[assign_stmt], orelse=[else_stmt])
        return if_node

    def _getter(self):
        func_name = f"{self.field_name}_getter"
        self_arg = ast.arg(arg="self", annotation=None)
        func_args = ast.arguments(
            args=[self_arg],
            kwonlyargs=[],
            vararg=None,
            kwarg=None,
            defaults=[],
            kw_defaults=[],
        )
        inst_var = ast.Attribute(
            value=ast.Name(id="self", ctx=ast.Load()),
            attr=f"_{self.field_name}",
            ctx=ast.Load(),
        )
        return_stmt = ast.Return(value=inst_var)
        func_node = ast.FunctionDef(
            name=func_name,
            args=func_args,
            body=[return_stmt],
            decorator_list=[],
            returns=None,
        )
        mod_node = ast.Module(body=[func_node])
        return ast_to_func(mod_node, func_name)

    def _setter(self, body):
        func_name = f"{self.field_name}_setter"
        self_arg = ast.arg(arg="self", annotation=None)
        new_arg = ast.arg(arg="new", annotation=None)
        func_args = ast.arguments(
            args=[self_arg, new_arg],
            kwonlyargs=[],
            vararg=None,
            kwarg=None,
            defaults=[],
            kw_defaults=[],
        )
        func_node = ast.FunctionDef(
            name=func_name, args=func_args, body=[body], decorator_list=[], returns=None
        )
        mod_node = ast.Module(body=[func_node])
        return ast_to_func(mod_node, func_name)

    def _except_msg(self):
        operators = {ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">="}
        lower_symbol = operators[self.bounds.left_op.__class__]
        upper_symbol = operators[self.bounds.right_op.__class__]
        msg = (
            f"{self.field_name} must be in the range "
            f"{self.bounds.lower_bound} {lower_symbol}"
            f" {self.field_name} "
            f"{upper_symbol} {self.bounds.upper_bound}"
        )
        return msg


def basic_func_args(*args):
    ast_args = ast.arguments(
        args=list(args),
        kwonlyargs=[],
        vararg=None,
        kwarg=None,
        defaults=[],
        kw_defaults=[],
    )
    return ast_args


def ast_to_func(node, name):
    ast.fix_missing_locations(node)
    code = compile(node, __file__, "exec")
    context = {}
    exec(code, globals(), context)
    return context[name]


def usemacros(cls):
    try:
        ann = cls.__annotations__
    except AttributeError:
        return cls

    for field, annotation in ann.items():
        macro_ast = ast.parse(annotation)
        macro_call = macro_ast.body[0].value
        name = macro_call.func.id
        if name not in globals():
            raise NameError(f"No macro with name '{name}' was found")
        macro = InRangeFactory(macro_call, field, cls)
        cls = macro.invoke()
    return cls


if __name__ == "__main__":

    @usemacros
    class Bar:
        x: "inrange(0 < x < 5)"
        z: "inrange(0 < z < 1)"

        def __init__(self, y):
            self.y = y

    bar = Bar(2)
    bar.x = 3
    bar.z = 2

"""Helpers to read KiCad symbol libraries (.kicad_sym) with sexpdata."""
import os
import sexpdata as S

Sym = S.Symbol


def load_lib(path):
    with open(path, encoding="utf-8") as f:
        return S.loads(f.read())


_lib_cache = {}


def lib_tree(path):
    if path not in _lib_cache:
        _lib_cache[path] = load_lib(path)
    return _lib_cache[path]


def find_symbol(tree, name):
    for it in tree[1:]:
        if isinstance(it, list) and it and it[0] == Sym("symbol") and it[1] == name:
            return it
    raise KeyError(name)


def _props(sym):
    return {it[1]: it for it in sym if isinstance(it, list) and it and it[0] == Sym("property")}


def resolve_symbol(tree, name, new_name, strip_v10=True):
    """Return a deep-copied symbol definition renamed to new_name with `extends` flattened."""
    import copy
    sym = copy.deepcopy(find_symbol(tree, name))
    ext = [it for it in sym if isinstance(it, list) and it and it[0] == Sym("extends")]
    if ext:
        base_name = ext[0][1]
        base = copy.deepcopy(find_symbol(tree, base_name))
        base_props = _props(base)
        for k, p in _props(sym).items():
            if k in base_props:
                idx = base.index(base_props[k])
                base[idx] = p
            else:
                base.append(p)
        # rename sub-units Base_0_1 -> Name_0_1
        for it in base:
            if isinstance(it, list) and it and it[0] == Sym("symbol") and isinstance(it[1], str):
                it[1] = it[1].replace(base_name, name, 1)
        sym = base
    # In .kicad_sch lib_symbols the top-level name carries the "Lib:" prefix but
    # the nested unit symbols keep their bare "Name_0_1" names.
    sym[1] = new_name
    return strip_v10_tokens(sym) if strip_v10 else sym


# Tokens introduced by the KiCad 10 library format that KiCad 9 refuses to parse.
_V10_TOKENS = {Sym("in_pos_files"), Sym("duplicate_pin_numbers_are_jumpers"),
               Sym("show_name"), Sym("do_not_autoplace"), Sym("jumper_pin_groups")}


def strip_v10_tokens(node):
    if not isinstance(node, list):
        return node
    return [strip_v10_tokens(it) for it in node
            if not (isinstance(it, list) and it and it[0] in _V10_TOKENS)]


def symbol_pins(sym):
    """Return list of dicts: number, name, type, x, y, angle (symbol coordinates, Y up)."""
    out = []

    def walk(node):
        for it in node:
            if isinstance(it, list) and it:
                if it[0] == Sym("symbol"):
                    walk(it)
                elif it[0] == Sym("pin"):
                    d = {"type": str(it[1])}
                    for p in it:
                        if isinstance(p, list):
                            if p[0] == Sym("name"):
                                d["name"] = p[1]
                            elif p[0] == Sym("number"):
                                d["number"] = str(p[1])
                            elif p[0] == Sym("at"):
                                d["x"], d["y"], d["angle"] = float(p[1]), float(p[2]), float(p[3])
                            elif p[0] == Sym("length"):
                                d["length"] = float(p[1])
                    out.append(d)
    walk(sym)
    return out


def dumps(node):
    return S.dumps(node)

from flask import Flask, render_template, request, jsonify, send_file
from io import BytesIO
from datetime import datetime
import re

app = Flask(__name__)

CAMPOS = {
    "NOMBRE": {"grupo":"mis_variables_texto","token":"VALOR_TEXTO","regex":r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]+","descripcion":"Nombre del paciente"},
    "APELLIDO": {"grupo":"mis_variables_texto","token":"VALOR_TEXTO","regex":r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]+","descripcion":"Apellido del paciente"},
    "DNI": {"grupo":"mis_variables_numericas","token":"VALOR_NUMERICO","regex":r"[0-9]{8}","descripcion":"Documento de identidad de 8 dígitos"},
    "EDAD": {"grupo":"mis_variables_numericas","token":"VALOR_NUMERICO","regex":r"[0-9]{1,3}","descripcion":"Edad del paciente"},
    "DIAGNOSTICO": {"grupo":"mis_variables_texto","token":"VALOR_TEXTO","regex":r"[A-Za-z0-9ÁÉÍÓÚáéíóúÑñÜü .,\-]+","descripcion":"Código o descripción del diagnóstico"},
    "FECHA": {"grupo":"mis_variables_fecha","token":"VALOR_FECHA","regex":r"[0-9]{4}-[0-9]{2}-[0-9]{2}","descripcion":"Fecha AAAA-MM-DD"},
    "HORA": {"grupo":"mis_variables_hora","token":"VALOR_HORA","regex":r"([01][0-9]|2[0-3]):[0-5][0-9]","descripcion":"Hora HH:MM"},
    "TIPO_SANGRE": {"grupo":"mis_variables_sanguineas","token":"VALOR_SANGUINEO","regex":r"(A|B|AB|O)[+-]","descripcion":"Tipo de sangre"},
    "EXAMENES": {"grupo":"mis_variables_texto","token":"VALOR_TEXTO","regex":r"[A-Za-z0-9ÁÉÍÓÚáéíóúÑñÜü ,.\-]+","descripcion":"Exámenes médicos"},
    "HOSPITAL_CLINICA": {"grupo":"mis_variables_texto","token":"VALOR_TEXTO","regex":r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü0-9 ,.\-]+","descripcion":"Hospital o clínica"},
    "LABORATORIO": {"grupo":"mis_variables_texto","token":"VALOR_TEXTO","regex":r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü0-9 ,.\-]+","descripcion":"Laboratorio"},
    "SALON": {"grupo":"mis_variables_texto","token":"VALOR_TEXTO","regex":r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü0-9\-]+","descripcion":"Código del salón"},
    "ENFERMERA_MEDICO": {"grupo":"mis_variables_texto","token":"VALOR_TEXTO","regex":r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]+","descripcion":"Personal médico"}
}
ORDEN_CAMPOS = list(CAMPOS)
ALIAS = {
    "HOSPITAL/CLINICA":"HOSPITAL_CLINICA", "HOSPITAL":"HOSPITAL_CLINICA",
    "CLINICA":"HOSPITAL_CLINICA", "TIPO SANGRE":"TIPO_SANGRE",
    "TIPO_DE_SANGRE":"TIPO_SANGRE", "ENFERMERA/MEDICO":"ENFERMERA_MEDICO",
    "ENFERMERA":"ENFERMERA_MEDICO", "MEDICO":"ENFERMERA_MEDICO",
    "EXAMEN":"EXAMENES"
}

# -------------------- ER -> AST -> AFND (Thompson) -> AFD (subconjuntos) --------------------

class RegexParser:
    def __init__(self, pattern):
        self.p = pattern
        self.i = 0

    def parse(self):
        node = self.alt()
        if self.i != len(self.p):
            raise ValueError(f"Símbolo inesperado en posición {self.i}: {self.p[self.i]}")
        return node

    def alt(self):
        parts = [self.concat()]
        while self.i < len(self.p) and self.p[self.i] == "|":
            self.i += 1
            parts.append(self.concat())
        return parts[0] if len(parts) == 1 else ("alt", parts)

    def concat(self):
        parts = []
        while self.i < len(self.p) and self.p[self.i] not in ")|":
            parts.append(self.repeat())
        if not parts:
            return ("eps",)
        return parts[0] if len(parts) == 1 else ("concat", parts)

    def repeat(self):
        node = self.atom()
        if self.i < len(self.p):
            c = self.p[self.i]
            if c in "*+?":
                self.i += 1
                node = ("repeat", node, c)
            elif c == "{":
                end = self.p.find("}", self.i)
                if end < 0:
                    raise ValueError("Cuantificador {m,n} sin cerrar")
                spec = self.p[self.i+1:end]
                self.i = end + 1
                m = re.fullmatch(r"(\d+)(?:,(\d*)?)?", spec)
                if not m:
                    raise ValueError(f"Cuantificador no soportado: {{{spec}}}")
                minimum = int(m.group(1))
                if "," not in spec:
                    maximum = minimum
                elif m.group(2) == "":
                    maximum = None
                else:
                    maximum = int(m.group(2))
                if maximum is not None and maximum < minimum:
                    raise ValueError("El máximo del cuantificador es menor que el mínimo")
                node = ("bounds", node, minimum, maximum)
        return node

    def atom(self):
        if self.i >= len(self.p):
            raise ValueError("Expresión regular incompleta")
        c = self.p[self.i]
        if c == "(":
            self.i += 1
            if self.p.startswith("?:", self.i):
                self.i += 2
            node = self.alt()
            if self.i >= len(self.p) or self.p[self.i] != ")":
                raise ValueError("Paréntesis sin cerrar")
            self.i += 1
            return node
        if c == "[":
            return ("chars", self.char_class())
        if c == "\\":
            self.i += 1
            if self.i >= len(self.p):
                raise ValueError("Escape incompleto")
            return ("chars", self.escape_set(self.p[self.i]))
        if c in "*+?{}":
            raise ValueError(f"Cuantificador inesperado: {c}")
        self.i += 1
        return ("chars", {c})

    def escape_set(self, c):
        if c == "d": return set("0123456789")
        if c == "w": return set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
        if c == "s": return set(" \t\r\n")
        return {c}

    def read_class_char(self):
        if self.i >= len(self.p):
            raise ValueError("Clase de caracteres sin cerrar")
        if self.p[self.i] == "\\":
            self.i += 1
            if self.i >= len(self.p): raise ValueError("Escape incompleto en clase")
            c = self.p[self.i]
            self.i += 1
            return c
        c = self.p[self.i]
        self.i += 1
        return c

    def char_class(self):
        self.i += 1
        negate = self.i < len(self.p) and self.p[self.i] == "^"
        if negate: self.i += 1
        chars = set()
        while self.i < len(self.p) and self.p[self.i] != "]":
            first = self.read_class_char()
            if self.i + 1 < len(self.p) and self.p[self.i] == "-" and self.p[self.i+1] != "]":
                self.i += 1
                last = self.read_class_char()
                if ord(last) < ord(first): raise ValueError("Rango inválido en clase")
                chars.update(chr(n) for n in range(ord(first), ord(last)+1))
            else:
                chars.add(first)
        if self.i >= len(self.p) or self.p[self.i] != "]":
            raise ValueError("Clase de caracteres sin cerrar")
        self.i += 1
        if negate:
            universe = set(chr(n) for n in range(32, 127))
            universe.update("ÁÉÍÓÚáéíóúÑñÜü")
            chars = universe - chars
        if not chars: raise ValueError("Clase de caracteres vacía")
        return chars

class Thompson:
    def __init__(self):
        self.edges = {}
        self.next_id = 0

    def state(self):
        s = self.next_id
        self.next_id += 1
        self.edges[s] = []
        return s

    def edge(self, a, b, symbol=None):
        self.edges[a].append({"to":b, "symbol":symbol})

    def build(self, node):
        kind = node[0]
        if kind == "eps":
            a, b = self.state(), self.state()
            self.edge(a, b, None)
            return a, b
        if kind == "chars":
            a, b = self.state(), self.state()
            for ch in sorted(node[1]):
                self.edge(a, b, ch)
            return a, b
        if kind == "concat":
            fragments = [self.build(part) for part in node[1]]
            for (_, end), (start, _) in zip(fragments, fragments[1:]):
                self.edge(end, start, None)
            return fragments[0][0], fragments[-1][1]
        if kind == "alt":
            a, b = self.state(), self.state()
            for part in node[1]:
                x, y = self.build(part)
                self.edge(a, x, None)
                self.edge(y, b, None)
            return a, b
        if kind == "repeat":
            child, op = node[1], node[2]
            a, b = self.state(), self.state()
            x, y = self.build(child)
            if op == "*":
                self.edge(a, b, None); self.edge(a, x, None)
                self.edge(y, x, None); self.edge(y, b, None)
            elif op == "+":
                self.edge(a, x, None); self.edge(y, x, None); self.edge(y, b, None)
            else:
                self.edge(a, b, None); self.edge(a, x, None); self.edge(y, b, None)
            return a, b
        if kind == "bounds":
            child, minimum, maximum = node[1], node[2], node[3]
            pieces = [self.build(child) for _ in range(minimum)]
            if maximum is None:
                star = self.build(("repeat", child, "*"))
                pieces.append(star)
            else:
                for _ in range(maximum - minimum):
                    opt = self.build(("repeat", child, "?"))
                    pieces.append(opt)
            if not pieces:
                return self.build(("eps",))
            for (_, end), (start, _) in zip(pieces, pieces[1:]):
                self.edge(end, start, None)
            return pieces[0][0], pieces[-1][1]
        raise ValueError(f"Nodo no soportado: {kind}")

def epsilon_closure(states, edges):
    result = set(states)
    stack = list(states)
    while stack:
        s = stack.pop()
        for e in edges[s]:
            if e["symbol"] is None and e["to"] not in result:
                result.add(e["to"])
                stack.append(e["to"])
    return result

def compile_automata(pattern):
    ast = RegexParser(pattern).parse()
    nfa = Thompson()
    start, accept = nfa.build(ast)
    alphabet = sorted({
        e["symbol"] for state_edges in nfa.edges.values()
        for e in state_edges if e["symbol"] is not None
    })
    dfa_sets = [frozenset(epsilon_closure({start}, nfa.edges))]
    dfa_index = {dfa_sets[0]: 0}
    dfa_transitions = []
    cursor = 0
    while cursor < len(dfa_sets):
        current = dfa_sets[cursor]
        row = {}
        for symbol in alphabet:
            moved = set()
            for s in current:
                for e in nfa.edges[s]:
                    if e["symbol"] == symbol:
                        moved.add(e["to"])
            if moved:
                closure = frozenset(epsilon_closure(moved, nfa.edges))
                if closure not in dfa_index:
                    dfa_index[closure] = len(dfa_sets)
                    dfa_sets.append(closure)
                row[symbol] = dfa_index[closure]
        dfa_transitions.append(row)
        cursor += 1

    nfa_states = []
    for s in sorted(nfa.edges):
        nfa_states.append({
            "id": f"n{s}",
            "accepting": s == accept,
            "transitions": [
                {"to":f"n{e['to']}", "symbol":"ε" if e["symbol"] is None else e["symbol"]}
                for e in nfa.edges[s]
            ]
        })

    # Completar el AFD con un estado pozo para que delta esté definida
    # para cada par (estado, símbolo) del alfabeto.
    dead_state = None
    for row in dfa_transitions:
        if any(symbol not in row for symbol in alphabet):
            dead_state = len(dfa_sets)
            break
    if dead_state is not None:
        for row in dfa_transitions:
            for symbol in alphabet:
                row.setdefault(symbol, dead_state)
        dfa_transitions.append({symbol: dead_state for symbol in alphabet})

    dfa_states = []
    dfa_delta = []
    total_dfa_states = len(dfa_transitions)
    for idx, subset in enumerate(dfa_sets):
        accepting = accept in subset
        dfa_states.append({
            "id":f"q{idx}",
            "accepting":accepting,
            "subset":[f"n{x}" for x in sorted(subset)]
        })
    if dead_state is not None:
        dfa_states.append({"id":f"q{dead_state}","accepting":False,"subset":["∅"],"dead":True})
    for idx, row in enumerate(dfa_transitions):
        for symbol, dest in sorted(row.items()):
            dfa_delta.append({"from":f"q{idx}","symbol":symbol,"to":f"q{dest}"})

    final_states = [f"q{i}" for i, subset in enumerate(dfa_sets) if accept in subset]
    quintuple = {
        "Q":[f"q{i}" for i in range(total_dfa_states)],
        "Sigma":alphabet,
        "delta":dfa_delta,
        "q0":"q0",
        "F":final_states
    }
    nfa_delta = [
        {"from":f"n{state}","symbol":"ε" if edge["symbol"] is None else edge["symbol"],"to":f"n{edge['to']}"}
        for state, edges in nfa.edges.items() for edge in edges
    ]
    nfa_quintuple = {
        "Q":[f"n{x}" for x in sorted(nfa.edges)],
        "Sigma":alphabet,
        "delta":nfa_delta,
        "q0":f"n{start}",
        "F":[f"n{accept}"]
    }
    return {
        "afnd":{"states":nfa_states,"start":f"n{start}","final":[f"n{accept}"],"quintuple":nfa_quintuple},
        "afd":{"states":dfa_states,"transitions":dfa_delta,"start":"q0","final":final_states},
        "alphabet":alphabet,
        "quintuple":quintuple,
        "transition_table":[
            {"estado":t["from"],"entrada":t["symbol"],"destino":t["to"]}
            for t in dfa_delta
        ]
    }


# -------------------- Lexer sintáctico + parser descendente (CFG) --------------------

GRAMATICA = [
    "S → REGISTRO",
    "REGISTRO → REGISTRO_MEDICO LLAVE_ABRE LISTA_CAMPOS LLAVE_CIERRA",
    "LISTA_CAMPOS → CAMPO LISTA_CAMPOS | ε",
    "CAMPO → IDENTIFICADOR DOS_PUNTOS VALOR",
    "VALOR → VALOR_TEXTO | VALOR_NUMERICO | VALOR_FECHA | VALOR_HORA | VALOR_SANGUINEO"
]

def tokenizar_sintaxis(texto):
    """Convierte el DSL en terminales con línea, lexema y tipo de valor."""
    tokens, errores = [], []
    lineas = texto.splitlines()
    dentro = False
    encontro_inicio = False
    encontro_cierre = False

    for numero, original in enumerate(lineas, 1):
        linea = original.strip()
        if not linea or linea.startswith("#"):
            continue
        if not encontro_inicio:
            if linea == "REGISTRO_MEDICO {":
                tokens.append({"tipo":"REGISTRO_MEDICO","lexema":"REGISTRO_MEDICO","linea":numero})
                tokens.append({"tipo":"LLAVE_ABRE","lexema":"{","linea":numero})
                encontro_inicio = True
                dentro = True
                continue
            if linea == "REGISTRO_MEDICO":
                tokens.append({"tipo":"REGISTRO_MEDICO","lexema":"REGISTRO_MEDICO","linea":numero})
                encontro_inicio = True
                continue
            errores.append(f"Línea {numero}: se esperaba la declaración REGISTRO_MEDICO {{.")
            continue
        if not dentro and tokens and tokens[-1]["tipo"] == "REGISTRO_MEDICO":
            if linea == "{":
                tokens.append({"tipo":"LLAVE_ABRE","lexema":"{","linea":numero})
                dentro = True
                continue
            errores.append(f"Línea {numero}: se esperaba la llave de apertura '{{'.")
            continue
        if dentro:
            if linea == "}":
                tokens.append({"tipo":"LLAVE_CIERRA","lexema":"}","linea":numero})
                dentro = False
                encontro_cierre = True
                continue
            if "{" in linea or "}" in linea:
                errores.append(f"Línea {numero}: llave inesperada dentro de la lista de campos.")
                continue
            if ":" not in linea:
                errores.append(f"Línea {numero}: se esperaba IDENTIFICADOR : VALOR.")
                continue
            nombre, valor = linea.split(":", 1)
            campo = normalizar_campo(nombre)
            valor = valor.strip().strip('"').strip("'")
            if not re.fullmatch(r"[A-Za-z_ÁÉÍÓÚáéíóúÑñÜü/ ]+", nombre.strip()):
                errores.append(f"Línea {numero}: identificador de campo inválido.")
                continue
            if campo not in CAMPOS:
                errores.append(f"Línea {numero}: identificador no declarado '{nombre.strip()}'.")
                continue
            tokens.extend([
                {"tipo":"IDENTIFICADOR","lexema":campo,"linea":numero},
                {"tipo":"DOS_PUNTOS","lexema":":","linea":numero},
                {"tipo":CAMPOS[campo]["token"],"lexema":valor,"linea":numero,"campo":campo}
            ])
        else:
            errores.append(f"Línea {numero}: contenido después del cierre del registro.")

    if not encontro_inicio:
        errores.append("Estructura: falta la declaración REGISTRO_MEDICO.")
    if encontro_inicio and not any(t["tipo"]=="LLAVE_ABRE" for t in tokens):
        errores.append("Estructura: falta la llave de apertura '{'.")
    if dentro or (encontro_inicio and not encontro_cierre):
        errores.append("Estructura: falta la llave de cierre '}'.")
    return tokens, errores

class ParserDSL:
    """Parser descendente que aplica las producciones de la gramática anterior."""
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.errores = []
        self.pasos = []

    def actual(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def consumir(self, tipo):
        token = self.actual()
        if token is None:
            self.errores.append(f"Fin inesperado: se esperaba {tipo}.")
            return {"tipo":tipo,"lexema":"<faltante>","linea":None}
        if token["tipo"] != tipo:
            self.errores.append(
                f"Línea {token.get('linea','?')}: se esperaba {tipo}, se encontró {token['tipo']} ('{token['lexema']}')."
            )
            return {"tipo":tipo,"lexema":"<error>","linea":token.get("linea")}
        self.pos += 1
        self.pasos.append(f"Reconocer {tipo}: {token['lexema']}")
        return token

    def parse(self):
        self.pasos.append("Expandir S → REGISTRO")
        raiz = {"nombre":"S","hijos":[self.registro()]}
        if self.pos < len(self.tokens):
            t = self.actual()
            self.errores.append(f"Línea {t.get('linea','?')}: token inesperado '{t['lexema']}' después del registro.")
        return raiz, self.errores

    def registro(self):
        self.pasos.append("Expandir REGISTRO → REGISTRO_MEDICO { LISTA_CAMPOS }")
        nodo = {"nombre":"REGISTRO","hijos":[]}
        t = self.consumir("REGISTRO_MEDICO")
        nodo["hijos"].append({"nombre":t["lexema"],"hijos":[]})
        t = self.consumir("LLAVE_ABRE")
        nodo["hijos"].append({"nombre":"{","hijos":[]})
        nodo["hijos"].append(self.lista_campos())
        t = self.consumir("LLAVE_CIERRA")
        nodo["hijos"].append({"nombre":"}","hijos":[]})
        return nodo

    def lista_campos(self):
        self.pasos.append("Expandir LISTA_CAMPOS → CAMPO LISTA_CAMPOS | ε")
        nodo = {"nombre":"LISTA_CAMPOS","hijos":[]}
        while self.actual() and self.actual()["tipo"] not in ("LLAVE_CIERRA",):
            before = self.pos
            nodo["hijos"].append(self.campo())
            if self.pos == before:
                self.pos += 1
        if not nodo["hijos"]:
            self.pasos.append("Aplicar LISTA_CAMPOS → ε")
            nodo["hijos"].append({"nombre":"ε","hijos":[]})
        else:
            self.pasos.append("Aplicar LISTA_CAMPOS → ε (fin de la lista)")
        return nodo

    def campo(self):
        self.pasos.append("Expandir CAMPO → IDENTIFICADOR : VALOR")
        nodo = {"nombre":"CAMPO","hijos":[]}
        identificador = self.consumir("IDENTIFICADOR")
        nombre = identificador.get("lexema","")
        nodo["hijos"].append({"nombre":f"IDENTIFICADOR ({nombre})","hijos":[]})
        nodo["hijos"].append({"nombre":self.consumir("DOS_PUNTOS")["lexema"],"hijos":[]})
        self.pasos.append("Expandir VALOR → VALOR_TEXTO | VALOR_NUMERICO | VALOR_FECHA | VALOR_HORA | VALOR_SANGUINEO")
        valor = self.actual()
        tipos_valor = ("VALOR_TEXTO","VALOR_NUMERICO","VALOR_FECHA","VALOR_HORA","VALOR_SANGUINEO")
        if valor and valor["tipo"] in tipos_valor:
            self.pos += 1
            self.pasos.append(f"Reconocer {valor['tipo']}: {valor['lexema']}")
            nodo["hijos"].append({"nombre":valor["tipo"],"hijos":[{"nombre":valor["lexema"],"hijos":[]}]})
        else:
            if valor is None:
                self.errores.append(f"Campo {nombre}: falta el valor.")
            else:
                self.errores.append(f"Línea {valor.get('linea','?')}: se esperaba un terminal VALOR para el campo {nombre}.")
                self.pos += 1
                nodo["hijos"].append({"nombre":"VALOR_INVALIDO","hijos":[{"nombre":valor["lexema"],"hijos":[]}]})
        return nodo

def analizar_sintaxis(texto):
    tokens, errores_lexicos = tokenizar_sintaxis(texto)
    parser = ParserDSL(tokens)
    arbol, errores_parser = parser.parse()
    return {
        "tokens_sintacticos":tokens,
        "errores_sintacticos":errores_lexicos + errores_parser,
        "arbol_derivacion":arbol,
        "gramatica":GRAMATICA,
        "pasos":parser.pasos
    }

# -------------------- Registro DSL y validaciones --------------------

def normalizar_campo(nombre):
    nombre = re.sub(r"\s+", "_", nombre.strip().upper())
    return ALIAS.get(nombre, nombre)

def extraer_registro(texto):
    datos, errores = {}, []
    lineas = texto.splitlines()
    if not any("REGISTRO_MEDICO" in x for x in lineas):
        errores.append("Estructura: falta la declaración REGISTRO_MEDICO.")
    if not any(x.strip() == "{" or x.strip() == "REGISTRO_MEDICO {" for x in lineas):
        errores.append("Estructura: falta la llave de apertura '{'.")
    if not any(x.strip() == "}" for x in lineas):
        errores.append("Estructura: falta la llave de cierre '}'.")
    for numero, linea in enumerate(lineas, 1):
        linea = linea.strip()
        if not linea or linea in ("{", "}", "REGISTRO_MEDICO {") or linea.startswith("#"):
            continue
        if ":" not in linea:
            errores.append(f"Línea {numero}: falta el separador ':'.")
            continue
        nombre, valor = linea.split(":", 1)
        campo = normalizar_campo(nombre)
        valor = valor.strip().strip('"').strip("'")
        if campo not in CAMPOS:
            errores.append(f"Línea {numero}: campo no reconocido '{nombre.strip()}'.")
            continue
        if campo in datos:
            errores.append(f"Línea {numero}: el campo '{campo}' está repetido.")
            continue
        datos[campo] = valor
    return datos, errores

def validar_fecha(valor):
    try:
        datetime.strptime(valor, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def analizar_registro(texto):
    datos, errores = extraer_registro(texto)
    tokens = []
    campos_reconocidos = []
    for campo in ORDEN_CAMPOS:
        if campo not in datos:
            continue
        cfg, valor = CAMPOS[campo], datos[campo]
        tokens.extend([
            {"token":"id_"+campo.lower(),"lexema":campo},
            {"token":"SEPARADOR","lexema":":"},
            {"token":cfg["token"],"lexema":valor}
        ])
        campos_reconocidos.append(campo)
        if not re.fullmatch(cfg["regex"], valor):
            errores.append(f"{campo}: el valor '{valor}' no cumple la expresión regular {cfg['regex']}.")
        if campo == "EDAD" and valor.isdigit() and not 1 <= int(valor) <= 120:
            errores.append("EDAD: debe estar entre 1 y 120 años.")
        if campo == "FECHA" and re.fullmatch(CAMPOS["FECHA"]["regex"], valor) and not validar_fecha(valor):
            errores.append("FECHA: la fecha no existe en el calendario.")
    faltantes = [c for c in ORDEN_CAMPOS if c not in datos]
    if faltantes:
        errores.append("Faltan campos obligatorios: " + ", ".join(faltantes))

    grupos = [
        {"token":"mis_variables_numericas","lexemas":"DNI, EDAD"},
        {"token":"mis_variables_texto","lexemas":"NOMBRE, APELLIDO, DIAGNOSTICO, EXAMENES, HOSPITAL_CLINICA, LABORATORIO, SALON, ENFERMERA_MEDICO"},
        {"token":"mis_variables_fecha","lexemas":"FECHA"},
        {"token":"mis_variables_hora","lexemas":"HORA"},
        {"token":"mis_variables_sanguineas","lexemas":"TIPO_SANGRE"},
        {"token":"separadores","lexemas":":"}
    ]
    expresiones = [{"lexema":c,"regex":CAMPOS[c]["regex"]} for c in ORDEN_CAMPOS]
    automatas = []
    for campo in ORDEN_CAMPOS:
        try:
            auto = compile_automata(CAMPOS[campo]["regex"])
            auto.update({"campo":campo,"regex":CAMPOS[campo]["regex"]})
            automatas.append(auto)
        except Exception as exc:
            automatas.append({"campo":campo,"regex":CAMPOS[campo]["regex"],"error":str(exc)})

    sintaxis = analizar_sintaxis(texto)
    for error_sintactico in sintaxis["errores_sintacticos"]:
        if error_sintactico not in errores:
            errores.append(error_sintactico)
    producciones = sintaxis["gramatica"]
    arbol = sintaxis["arbol_derivacion"]
    return {
        "valido":len(errores)==0,"datos":datos,"tokens":tokens,
        "total_tokens":len(tokens),"campos_reconocidos":len(campos_reconocidos),
        "total_campos":len(ORDEN_CAMPOS),"errores":errores,
        "grupos":grupos,"expresiones":expresiones,"automatas":automatas,
         "producciones":producciones,"arbol":arbol,"faltantes":faltantes,
        "tokens_sintacticos":sintaxis["tokens_sintacticos"],
        "errores_sintacticos":sintaxis["errores_sintacticos"],
        "pasos_sintacticos":sintaxis["pasos"],
        "estado":"Registro válido" if not errores else "Registro con observaciones"
    }

@app.route("/")
def inicio():
    return render_template("index.html")

@app.route("/analizar", methods=["POST"])
def analizar():
    payload = request.get_json(silent=True) or {}
    texto = payload.get("texto", "")
    if not isinstance(texto, str) or not texto.strip():
        return jsonify({"mensaje":"Ingresa un registro médico para analizar."}), 400
    return jsonify(analizar_registro(texto))

@app.route("/descargar-pdf", methods=["POST"])
def descargar_pdf():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    payload = request.get_json(silent=True) or {}
    resultado = payload.get("resultado")
    if not resultado:
        return jsonify({"mensaje":"Primero debes analizar un registro."}), 400
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    story = [Paragraph("RuleCheck - Reporte de análisis", styles["Title"]), Spacer(1,10)]
    story.append(Paragraph(f"<b>Estado:</b> {resultado.get('estado','')}", styles["Normal"]))
    story.append(Paragraph(f"<b>Tokens:</b> {resultado.get('total_tokens',0)} | <b>Campos:</b> {resultado.get('campos_reconocidos',0)}/{resultado.get('total_campos',0)}", styles["Normal"]))
    story.append(Spacer(1,10))
    story.append(Paragraph("Agrupación de tokens y lexemas", styles["Heading2"]))
    rows = [["Token (Agrupador)","Lexemas"]]
    for g in resultado.get("grupos",[]): rows.append([g["token"],g["lexemas"]])
    t = Table(rows, colWidths=[155,350], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#174f7d")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.4,colors.grey),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(t)
    story.append(Spacer(1,10))
    story.append(Paragraph("Tokens individuales", styles["Heading2"]))
    rows = [["Token","Lexema"]]+[[x["token"],x["lexema"]] for x in resultado.get("tokens",[])]
    t = Table(rows, colWidths=[180,325], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#174f7d")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.4,colors.grey),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(t)
    story.append(Spacer(1,10))
    story.append(Paragraph("Expresiones regulares", styles["Heading2"]))
    er_rows = [["Campo", "Expresión regular"]] + [[x.get("lexema",""), x.get("regex","")] for x in resultado.get("expresiones",[])]
    er_table = Table(er_rows, colWidths=[130,375], repeatRows=1)
    er_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#174f7d")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.4,colors.grey),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(er_table)
    for auto in resultado.get("automatas",[]):
        if auto.get("error"):
            continue
        story.append(Spacer(1,8))
        story.append(Paragraph(f"Autómatas del campo {auto.get('campo','')}", styles["Heading3"]))
        q = auto.get("quintuple",{})
        q_text = f"Q={q.get('Q',[])} | Sigma={q.get('Sigma',[])} | q0={q.get('q0','')} | F={q.get('F',[])}"
        story.append(Paragraph(q_text, styles["Normal"]))
        tr_rows = [["Estado actual","Entrada","Estado destino"]]
        tr_rows += [[x.get("estado",""), x.get("entrada",""), x.get("destino","")] for x in auto.get("transition_table",[])]
        tr_table = Table(tr_rows, colWidths=[150,205,150], repeatRows=1)
        tr_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#dce8f3")),("GRID",(0,0),(-1,-1),.3,colors.grey),("FONTSIZE",(0,0),(-1,-1),7),("VALIGN",(0,0),(-1,-1),"TOP")]))
        story.append(tr_table)
    story.append(Spacer(1,10))
    story.append(Paragraph("Análisis sintáctico - Gramática libre de contexto", styles["Heading2"]))
    for prod in resultado.get("producciones", []):
        story.append(Paragraph(prod.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"), styles["Code"]))
    story.append(Paragraph("Resultado sintáctico: " + ("Cadena aceptada" if not resultado.get("errores_sintacticos") else "Cadena rechazada"), styles["Normal"]))
    story.append(Paragraph("Árbol de derivación", styles["Heading2"]))
    def flatten_tree(node, depth=0):
        lines = [("    " * depth) + str(node.get("nombre",""))]
        for child in node.get("hijos", []):
            lines.extend(flatten_tree(child, depth+1))
        return lines
    for line in flatten_tree(resultado.get("arbol", {})):
        story.append(Paragraph(line.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace(" ","&nbsp;"), styles["Code"]))
    story.append(Spacer(1,10))
    story.append(Paragraph("Errores y observaciones", styles["Heading2"]))
    for e in resultado.get("errores",[]) or ["No se encontraron errores."]:
        story.append(Paragraph("• "+e, styles["Normal"]))
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="reporte_rulecheck.pdf", mimetype="application/pdf")

if __name__ == "__main__":
    app.run(debug=True)

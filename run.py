from flask import Flask, render_template, request, jsonify, send_file
from io import BytesIO
from datetime import datetime
import re

app = Flask(__name__)

# ============================================================
# CONFIGURACIÓN DE CAMPOS DEL DSL
# ============================================================

CAMPOS = {
    "NOMBRE": {
        "grupo": "mis_variables_texto",
        "token": "VALOR_TEXTO",
        "regex": r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]+",
        "descripcion": "Nombre del paciente"
    },
    "APELLIDO": {
        "grupo": "mis_variables_texto",
        "token": "VALOR_TEXTO",
        "regex": r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]+",
        "descripcion": "Apellido del paciente"
    },
    "DNI": {
        "grupo": "mis_variables_numericas",
        "token": "VALOR_NUMERICO",
        "regex": r"[0-9]{8}",
        "descripcion": "Documento de identidad de 8 dígitos"
    },
    "EDAD": {
        "grupo": "mis_variables_numericas",
        "token": "VALOR_NUMERICO",
        "regex": r"[0-9]{1,3}",
        "descripcion": "Edad del paciente"
    },
    "DIAGNOSTICO": {
        "grupo": "mis_variables_texto",
        "token": "VALOR_TEXTO",
        "regex": r"[A-Za-z0-9ÁÉÍÓÚáéíóúÑñÜü .,\-]+",
        "descripcion": "Código o descripción del diagnóstico"
    },
    "FECHA": {
        "grupo": "mis_variables_fecha",
        "token": "VALOR_FECHA",
        "regex": r"[0-9]{4}-[0-9]{2}-[0-9]{2}",
        "descripcion": "Fecha AAAA-MM-DD"
    },
    "HORA": {
        "grupo": "mis_variables_hora",
        "token": "VALOR_HORA",
        "regex": r"([01][0-9]|2[0-3]):[0-5][0-9]",
        "descripcion": "Hora HH:MM"
    },
    "TIPO_SANGRE": {
        "grupo": "mis_variables_sanguineas",
        "token": "VALOR_SANGUINEO",
        "regex": r"(A|B|AB|O)[+-]",
        "descripcion": "Tipo de sangre"
    },
    "EXAMENES": {
        "grupo": "mis_variables_texto",
        "token": "VALOR_TEXTO",
        "regex": r"[A-Za-z0-9ÁÉÍÓÚáéíóúÑñÜü ,.\-]+",
        "descripcion": "Exámenes médicos"
    },
    "HOSPITAL_CLINICA": {
        "grupo": "mis_variables_texto",
        "token": "VALOR_TEXTO",
        "regex": r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü0-9 ,.\-]+",
        "descripcion": "Hospital o clínica"
    },
    "LABORATORIO": {
        "grupo": "mis_variables_texto",
        "token": "VALOR_TEXTO",
        "regex": r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü0-9 ,.\-]+",
        "descripcion": "Laboratorio"
    },
    "SALON": {
        "grupo": "mis_variables_texto",
        "token": "VALOR_TEXTO",
        "regex": r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü0-9\-]+",
        "descripcion": "Código del salón"
    },
    "ENFERMERA_MEDICO": {
        "grupo": "mis_variables_texto",
        "token": "VALOR_TEXTO",
        "regex": r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]+",
        "descripcion": "Personal médico"
    }
}

ORDEN_CAMPOS = list(CAMPOS)

ALIAS = {
    "HOSPITAL/CLINICA": "HOSPITAL_CLINICA",
    "HOSPITAL": "HOSPITAL_CLINICA",
    "CLINICA": "HOSPITAL_CLINICA",
    "TIPO SANGRE": "TIPO_SANGRE",
    "TIPO_DE_SANGRE": "TIPO_SANGRE",
    "ENFERMERA/MEDICO": "ENFERMERA_MEDICO",
    "ENFERMERA": "ENFERMERA_MEDICO",
    "MEDICO": "ENFERMERA_MEDICO",
    "EXAMEN": "EXAMENES"
}


# ============================================================
# AUTÓMATAS: ER -> AFND -> AFD
# ============================================================

class RegexParser:

    def __init__(self, pattern):
        self.p = pattern
        self.i = 0

    def parse(self):
        node = self.alt()

        if self.i != len(self.p):
            raise ValueError(
                f"Símbolo inesperado en posición {self.i}"
            )

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
                    raise ValueError("Cuantificador sin cerrar")

                spec = self.p[self.i + 1:end]
                self.i = end + 1

                m = re.fullmatch(r"(\d+)(?:,(\d*)?)?", spec)

                if not m:
                    raise ValueError("Cuantificador no soportado")

                minimum = int(m.group(1))

                if "," not in spec:
                    maximum = minimum
                elif m.group(2) == "":
                    maximum = None
                else:
                    maximum = int(m.group(2))

                if maximum is not None and maximum < minimum:
                    raise ValueError("Rango inválido")

                node = ("bounds", node, minimum, maximum)

        return node

    def atom(self):
        if self.i >= len(self.p):
            raise ValueError("Expresión incompleta")

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
        if c == "d":
            return set("0123456789")

        if c == "w":
            return set(
                "abcdefghijklmnopqrstuvwxyz"
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                "0123456789_"
            )

        if c == "s":
            return set(" \t\r\n")

        return {c}

    def read_class_char(self):
        if self.i >= len(self.p):
            raise ValueError("Clase sin cerrar")

        if self.p[self.i] == "\\":
            self.i += 1

            if self.i >= len(self.p):
                raise ValueError("Escape incompleto")

            c = self.p[self.i]
            self.i += 1
            return c

        c = self.p[self.i]
        self.i += 1
        return c

    def char_class(self):
        self.i += 1

        negate = (
            self.i < len(self.p)
            and self.p[self.i] == "^"
        )

        if negate:
            self.i += 1

        chars = set()

        while self.i < len(self.p) and self.p[self.i] != "]":
            first = self.read_class_char()

            if (
                self.i + 1 < len(self.p)
                and self.p[self.i] == "-"
                and self.p[self.i + 1] != "]"
            ):
                self.i += 1
                last = self.read_class_char()

                if ord(last) < ord(first):
                    raise ValueError("Rango inválido")

                chars.update(
                    chr(n)
                    for n in range(ord(first), ord(last) + 1)
                )
            else:
                chars.add(first)

        if self.i >= len(self.p):
            raise ValueError("Clase sin cerrar")

        self.i += 1

        if negate:
            universe = set(chr(n) for n in range(32, 127))
            universe.update("ÁÉÍÓÚáéíóúÑñÜü")
            chars = universe - chars

        if not chars:
            raise ValueError("Clase vacía")

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
        self.edges[a].append({
            "to": b,
            "symbol": symbol
        })

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
            fragments = [
                self.build(part)
                for part in node[1]
            ]

            for (_, end), (start, _) in zip(
                fragments,
                fragments[1:]
            ):
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
                self.edge(a, b, None)
                self.edge(a, x, None)
                self.edge(y, x, None)
                self.edge(y, b, None)

            elif op == "+":
                self.edge(a, x, None)
                self.edge(y, x, None)
                self.edge(y, b, None)

            else:
                self.edge(a, b, None)
                self.edge(a, x, None)
                self.edge(y, b, None)

            return a, b

        if kind == "bounds":
            child, minimum, maximum = node[1], node[2], node[3]

            pieces = [
                self.build(child)
                for _ in range(minimum)
            ]

            if maximum is None:
                pieces.append(
                    self.build(("repeat", child, "*"))
                )
            else:
                for _ in range(maximum - minimum):
                    pieces.append(
                        self.build(("repeat", child, "?"))
                    )

            if not pieces:
                return self.build(("eps",))

            for (_, end), (start, _) in zip(
                pieces,
                pieces[1:]
            ):
                self.edge(end, start, None)

            return pieces[0][0], pieces[-1][1]

        raise ValueError(f"Nodo no soportado: {kind}")


def epsilon_closure(states, edges):
    result = set(states)
    stack = list(states)

    while stack:
        s = stack.pop()

        for edge in edges[s]:
            if (
                edge["symbol"] is None
                and edge["to"] not in result
            ):
                result.add(edge["to"])
                stack.append(edge["to"])

    return result


def compile_automata(pattern):
    ast = RegexParser(pattern).parse()

    nfa = Thompson()
    start, accept = nfa.build(ast)

    alphabet = sorted({
        edge["symbol"]
        for state_edges in nfa.edges.values()
        for edge in state_edges
        if edge["symbol"] is not None
    })

    dfa_sets = [
        frozenset(
            epsilon_closure({start}, nfa.edges)
        )
    ]

    dfa_index = {dfa_sets[0]: 0}
    dfa_transitions = []
    cursor = 0

    while cursor < len(dfa_sets):
        current = dfa_sets[cursor]
        row = {}

        for symbol in alphabet:
            moved = set()

            for state in current:
                for edge in nfa.edges[state]:
                    if edge["symbol"] == symbol:
                        moved.add(edge["to"])

            if moved:
                closure = frozenset(
                    epsilon_closure(moved, nfa.edges)
                )

                if closure not in dfa_index:
                    dfa_index[closure] = len(dfa_sets)
                    dfa_sets.append(closure)

                row[symbol] = dfa_index[closure]

        dfa_transitions.append(row)
        cursor += 1

    nfa_states = []

    for state in sorted(nfa.edges):
        nfa_states.append({
            "id": f"n{state}",
            "accepting": state == accept,
            "transitions": [
                {
                    "to": f"n{edge['to']}",
                    "symbol": (
                        "ε"
                        if edge["symbol"] is None
                        else edge["symbol"]
                    )
                }
                for edge in nfa.edges[state]
            ]
        })

    dead_state = None

    for row in dfa_transitions:
        if any(symbol not in row for symbol in alphabet):
            dead_state = len(dfa_sets)
            break

    if dead_state is not None:
        for row in dfa_transitions:
            for symbol in alphabet:
                row.setdefault(symbol, dead_state)

        dfa_transitions.append({
            symbol: dead_state
            for symbol in alphabet
        })

    dfa_states = []
    dfa_delta = []
    total_dfa_states = len(dfa_transitions)

    for idx, subset in enumerate(dfa_sets):
        dfa_states.append({
            "id": f"q{idx}",
            "accepting": accept in subset,
            "subset": [f"n{x}" for x in sorted(subset)]
        })

    if dead_state is not None:
        dfa_states.append({
            "id": f"q{dead_state}",
            "accepting": False,
            "subset": ["∅"],
            "dead": True
        })

    for idx, row in enumerate(dfa_transitions):
        for symbol, dest in sorted(row.items()):
            dfa_delta.append({
                "from": f"q{idx}",
                "symbol": symbol,
                "to": f"q{dest}"
            })

    final_states = [
        f"q{i}"
        for i, subset in enumerate(dfa_sets)
        if accept in subset
    ]

    quintuple = {
        "Q": [f"q{i}" for i in range(total_dfa_states)],
        "Sigma": alphabet,
        "delta": dfa_delta,
        "q0": "q0",
        "F": final_states
    }

    nfa_delta = [
        {
            "from": f"n{state}",
            "symbol": (
                "ε"
                if edge["symbol"] is None
                else edge["symbol"]
            ),
            "to": f"n{edge['to']}"
        }
        for state, edges in nfa.edges.items()
        for edge in edges
    ]

    nfa_quintuple = {
        "Q": [f"n{x}" for x in sorted(nfa.edges)],
        "Sigma": alphabet,
        "delta": nfa_delta,
        "q0": f"n{start}",
        "F": [f"n{accept}"]
    }

    return {
        "afnd": {
            "states": nfa_states,
            "start": f"n{start}",
            "final": [f"n{accept}"],
            "quintuple": nfa_quintuple
        },
        "afd": {
            "states": dfa_states,
            "transitions": dfa_delta,
            "start": "q0",
            "final": final_states
        },
        "alphabet": alphabet,
        "quintuple": quintuple,
        "transition_table": [
            {
                "estado": t["from"],
                "entrada": t["symbol"],
                "destino": t["to"]
            }
            for t in dfa_delta
        ]
    }


# ============================================================
# ANÁLISIS SINTÁCTICO
# ============================================================

GRAMATICA = [
    "S → REGISTRO",
    "REGISTRO → REGISTRO_MEDICO LLAVE_ABRE LISTA_CAMPOS LLAVE_CIERRA",
    "LISTA_CAMPOS → CAMPO LISTA_CAMPOS | ε",
    "CAMPO → IDENTIFICADOR DOS_PUNTOS VALOR",
    "VALOR → VALOR_TEXTO | VALOR_NUMERICO | VALOR_FECHA | VALOR_HORA | VALOR_SANGUINEO"
]


def normalizar_campo(nombre):
    nombre = re.sub(
        r"\s+",
        "_",
        nombre.strip().upper()
    )

    return ALIAS.get(nombre, nombre)


def tokenizar_sintaxis(texto):
    tokens = []
    errores = []

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
                tokens.append({
                    "tipo": "REGISTRO_MEDICO",
                    "lexema": "REGISTRO_MEDICO",
                    "linea": numero
                })

                tokens.append({
                    "tipo": "LLAVE_ABRE",
                    "lexema": "{",
                    "linea": numero
                })

                encontro_inicio = True
                dentro = True
                continue

            if linea == "REGISTRO_MEDICO":
                tokens.append({
                    "tipo": "REGISTRO_MEDICO",
                    "lexema": "REGISTRO_MEDICO",
                    "linea": numero
                })

                encontro_inicio = True
                continue

            errores.append(
                f"Línea {numero}: se esperaba REGISTRO_MEDICO {{."
            )
            continue

        if not dentro and tokens[-1]["tipo"] == "REGISTRO_MEDICO":
            if linea == "{":
                tokens.append({
                    "tipo": "LLAVE_ABRE",
                    "lexema": "{",
                    "linea": numero
                })

                dentro = True
                continue

            errores.append(
                f"Línea {numero}: falta la llave de apertura."
            )
            continue

        if dentro:
            if linea == "}":
                tokens.append({
                    "tipo": "LLAVE_CIERRA",
                    "lexema": "}",
                    "linea": numero
                })

                dentro = False
                encontro_cierre = True
                continue

            if "{" in linea or "}" in linea:
                errores.append(
                    f"Línea {numero}: llave inesperada."
                )
                continue

            if ":" not in linea:
                errores.append(
                    f"Línea {numero}: se esperaba IDENTIFICADOR : VALOR."
                )
                continue

            nombre, valor = linea.split(":", 1)
            campo = normalizar_campo(nombre)
            valor = valor.strip().strip('"').strip("'")

            if not re.fullmatch(
                r"[A-Za-z_ÁÉÍÓÚáéíóúÑñÜü/ ]+",
                nombre.strip()
            ):
                errores.append(
                    f"Línea {numero}: identificador inválido."
                )
                continue

            if campo not in CAMPOS:
                errores.append(
                    f"Línea {numero}: campo no declarado '{nombre.strip()}'."
                )
                continue

            tokens.extend([
                {
                    "tipo": "IDENTIFICADOR",
                    "lexema": campo,
                    "linea": numero
                },
                {
                    "tipo": "DOS_PUNTOS",
                    "lexema": ":",
                    "linea": numero
                },
                {
                    "tipo": CAMPOS[campo]["token"],
                    "lexema": valor,
                    "linea": numero,
                    "campo": campo
                }
            ])

        else:
            errores.append(
                f"Línea {numero}: contenido después del cierre."
            )

    if not encontro_inicio:
        errores.append(
            "Estructura: falta REGISTRO_MEDICO."
        )

    if encontro_inicio and not any(
        t["tipo"] == "LLAVE_ABRE"
        for t in tokens
    ):
        errores.append(
            "Estructura: falta la llave de apertura '{'."
        )

    if dentro or (encontro_inicio and not encontro_cierre):
        errores.append(
            "Estructura: falta la llave de cierre '}'."
        )

    return tokens, errores


class ParserDSL:

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.errores = []
        self.pasos = []

    def actual(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]

        return None

    def consumir(self, tipo):
        token = self.actual()

        if token is None:
            self.errores.append(
                f"Fin inesperado: se esperaba {tipo}."
            )

            return {
                "tipo": tipo,
                "lexema": "<faltante>",
                "linea": None
            }

        if token["tipo"] != tipo:
            self.errores.append(
                f"Línea {token.get('linea', '?')}: "
                f"se esperaba {tipo}, se encontró "
                f"{token['tipo']}."
            )

            return {
                "tipo": tipo,
                "lexema": "<error>",
                "linea": token.get("linea")
            }

        self.pos += 1

        self.pasos.append(
            f"Reconocer {tipo}: {token['lexema']}"
        )

        return token

    def parse(self):
        self.pasos.append("Expandir S → REGISTRO")

        raiz = {
            "nombre": "S",
            "hijos": [self.registro()]
        }

        if self.pos < len(self.tokens):
            token = self.actual()

            self.errores.append(
                f"Línea {token.get('linea', '?')}: "
                "token inesperado después del registro."
            )

        return raiz, self.errores

    def registro(self):
        self.pasos.append(
            "Expandir REGISTRO → REGISTRO_MEDICO { LISTA_CAMPOS }"
        )

        nodo = {
            "nombre": "REGISTRO",
            "hijos": []
        }

        token = self.consumir("REGISTRO_MEDICO")

        nodo["hijos"].append({
            "nombre": token["lexema"],
            "hijos": []
        })

        self.consumir("LLAVE_ABRE")

        nodo["hijos"].append({
            "nombre": "{",
            "hijos": []
        })

        nodo["hijos"].append(self.lista_campos())

        self.consumir("LLAVE_CIERRA")

        nodo["hijos"].append({
            "nombre": "}",
            "hijos": []
        })

        return nodo

    def lista_campos(self):
        self.pasos.append(
            "Expandir LISTA_CAMPOS → CAMPO LISTA_CAMPOS | ε"
        )

        nodo = {
            "nombre": "LISTA_CAMPOS",
            "hijos": []
        }

        while (
            self.actual()
            and self.actual()["tipo"] != "LLAVE_CIERRA"
        ):
            anterior = self.pos
            nodo["hijos"].append(self.campo())

            if self.pos == anterior:
                self.pos += 1

        if not nodo["hijos"]:
            self.pasos.append(
                "Aplicar LISTA_CAMPOS → ε"
            )

            nodo["hijos"].append({
                "nombre": "ε",
                "hijos": []
            })

        return nodo

    def campo(self):
        self.pasos.append(
            "Expandir CAMPO → IDENTIFICADOR : VALOR"
        )

        nodo = {
            "nombre": "CAMPO",
            "hijos": []
        }

        identificador = self.consumir("IDENTIFICADOR")
        nombre = identificador.get("lexema", "")

        nodo["hijos"].append({
            "nombre": f"IDENTIFICADOR ({nombre})",
            "hijos": []
        })

        separador = self.consumir("DOS_PUNTOS")

        nodo["hijos"].append({
            "nombre": separador["lexema"],
            "hijos": []
        })

        self.pasos.append(
            "Expandir VALOR → VALOR_TEXTO | VALOR_NUMERICO | "
            "VALOR_FECHA | VALOR_HORA | VALOR_SANGUINEO"
        )

        valor = self.actual()

        tipos = (
            "VALOR_TEXTO",
            "VALOR_NUMERICO",
            "VALOR_FECHA",
            "VALOR_HORA",
            "VALOR_SANGUINEO"
        )

        if valor and valor["tipo"] in tipos:
            self.pos += 1

            self.pasos.append(
                f"Reconocer {valor['tipo']}: {valor['lexema']}"
            )

            nodo["hijos"].append({
                "nombre": valor["tipo"],
                "hijos": [{
                    "nombre": valor["lexema"],
                    "hijos": []
                }]
            })

        else:
            if valor is None:
                self.errores.append(
                    f"Campo {nombre}: falta el valor."
                )
            else:
                self.errores.append(
                    f"Línea {valor.get('linea', '?')}: "
                    f"valor inválido para {nombre}."
                )

                self.pos += 1

                nodo["hijos"].append({
                    "nombre": "VALOR_INVALIDO",
                    "hijos": [{
                        "nombre": valor["lexema"],
                        "hijos": []
                    }]
                })

        return nodo


def analizar_sintaxis(texto):
    tokens, errores_lexicos = tokenizar_sintaxis(texto)

    parser = ParserDSL(tokens)
    arbol, errores_parser = parser.parse()

    return {
        "tokens_sintacticos": tokens,
        "errores_sintacticos": (
            errores_lexicos + errores_parser
        ),
        "arbol_derivacion": arbol,
        "gramatica": GRAMATICA,
        "pasos": parser.pasos
    }


# ============================================================
# EXTRACCIÓN Y VALIDACIÓN DEL REGISTRO
# ============================================================

def extraer_registro(texto):
    datos = {}
    errores = []

    lineas = texto.splitlines()

    if not any(
        "REGISTRO_MEDICO" in linea
        for linea in lineas
    ):
        errores.append(
            "Estructura: falta REGISTRO_MEDICO."
        )

    if not any(
        linea.strip() in ("{", "REGISTRO_MEDICO {")
        for linea in lineas
    ):
        errores.append(
            "Estructura: falta la llave de apertura '{'."
        )

    if not any(
        linea.strip() == "}"
        for linea in lineas
    ):
        errores.append(
            "Estructura: falta la llave de cierre '}'."
        )

    for numero, linea in enumerate(lineas, 1):
        linea = linea.strip()

        if (
            not linea
            or linea in ("{", "}", "REGISTRO_MEDICO {")
            or linea.startswith("#")
        ):
            continue

        if ":" not in linea:
            errores.append(
                f"Línea {numero}: falta el separador ':'."
            )
            continue

        nombre, valor = linea.split(":", 1)

        campo = normalizar_campo(nombre)
        valor = valor.strip().strip('"').strip("'")

        if campo not in CAMPOS:
            errores.append(
                f"Línea {numero}: campo no reconocido "
                f"'{nombre.strip()}'."
            )
            continue

        if campo in datos:
            errores.append(
                f"Línea {numero}: el campo '{campo}' está repetido."
            )
            continue

        datos[campo] = valor

    return datos, errores


def validar_fecha(valor):
    try:
        datetime.strptime(valor, "%Y-%m-%d")
        return True
    except ValueError:
        return False


# ============================================================
# 3.4 ANÁLISIS SEMÁNTICO
# ============================================================

def analizar_semantica(datos):

    semantica = []
    errores = []

    atributos_heredados = {
        "tipo_registro": "REGISTRO_MEDICO",
        "campos_obligatorios": ORDEN_CAMPOS
    }

    atributos_sintetizados = {
        "registro_completo": True,
        "cantidad_campos": len(datos),
        "cantidad_campos_validos": 0,
        "cantidad_errores": 0
    }

    hijos_arbol = []

    reglas = {
        "NOMBRE": "Debe contener únicamente letras y espacios.",
        "APELLIDO": "Debe contener únicamente letras y espacios.",
        "DNI": "Debe contener exactamente 8 dígitos.",
        "EDAD": "Debe ser un número entre 1 y 120.",
        "DIAGNOSTICO": "Debe contener caracteres válidos.",
        "FECHA": "Debe ser una fecha real con formato AAAA-MM-DD.",
        "HORA": "Debe tener formato HH:MM y hora válida.",
        "TIPO_SANGRE": "Debe ser un grupo sanguíneo válido.",
        "EXAMENES": "Debe contener texto válido.",
        "HOSPITAL_CLINICA": "Debe identificar un centro de atención.",
        "LABORATORIO": "Debe identificar el laboratorio.",
        "SALON": "Debe contener un código válido.",
        "ENFERMERA_MEDICO": "Debe identificar al profesional responsable."
    }

    for campo in ORDEN_CAMPOS:

        valor = datos.get(campo)
        configuracion = CAMPOS[campo]

        valido = (
            valor is not None
            and valor != ""
            and bool(
                re.fullmatch(
                    configuracion["regex"],
                    valor
                )
            )
        )

        if campo == "EDAD" and valido:
            valido = 1 <= int(valor) <= 120

        if campo == "FECHA" and valido:
            valido = validar_fecha(valor)

        estado = "VÁLIDO" if valido else "INVÁLIDO"

        if valido:
            atributos_sintetizados[
                "cantidad_campos_validos"
            ] += 1
        else:
            errores.append(
                f"Error semántico en {campo}: "
                "valor ausente o inválido."
            )

            atributos_sintetizados[
                "registro_completo"
            ] = False

        semantica.append({
            "campo": campo,
            "tipo": configuracion["token"],
            "valor": valor if valor is not None else "—",
            "regla": reglas[campo],
            "estado": estado
        })

        hijos_arbol.append({
            "nombre": (
                f"{campo}: "
                f"{valor if valor is not None else 'AUSENTE'}"
            ),
            "hijos": [
                {
                    "nombre": f"Tipo: {configuracion['token']}",
                    "hijos": []
                },
                {
                    "nombre": f"Regla: {reglas[campo]}",
                    "hijos": []
                },
                {
                    "nombre": f"Estado: {estado}",
                    "hijos": []
                }
            ]
        })

    atributos_sintetizados["cantidad_errores"] = len(errores)

    arbol_semantico = {
        "nombre": "REGISTRO_MEDICO",
        "hijos": hijos_arbol
    }

    return {
        "semantica": semantica,
        "atributos_heredados": atributos_heredados,
        "atributos_sintetizados": atributos_sintetizados,
        "arbol_semantico": arbol_semantico,
        "errores_semanticos": errores
    }


# ============================================================
# ANÁLISIS GENERAL DEL COMPILADOR
# ============================================================

def analizar_registro(texto):

    datos, errores = extraer_registro(texto)

    tokens = []
    campos_reconocidos = []

    for campo in ORDEN_CAMPOS:

        if campo not in datos:
            continue

        configuracion = CAMPOS[campo]
        valor = datos[campo]

        tokens.extend([
            {
                "token": "id_" + campo.lower(),
                "lexema": campo
            },
            {
                "token": "SEPARADOR",
                "lexema": ":"
            },
            {
                "token": configuracion["token"],
                "lexema": valor
            }
        ])

        campos_reconocidos.append(campo)

        if not re.fullmatch(configuracion["regex"], valor):
            errores.append(
                f"{campo}: el valor '{valor}' no cumple "
                f"la expresión regular {configuracion['regex']}."
            )

        if campo == "EDAD" and valor.isdigit():
            if not 1 <= int(valor) <= 120:
                errores.append(
                    "EDAD: debe estar entre 1 y 120 años."
                )

        if campo == "FECHA":
            if (
                re.fullmatch(CAMPOS["FECHA"]["regex"], valor)
                and not validar_fecha(valor)
            ):
                errores.append(
                    "FECHA: la fecha no existe en el calendario."
                )

    faltantes = [
        campo
        for campo in ORDEN_CAMPOS
        if campo not in datos
    ]

    if faltantes:
        errores.append(
            "Faltan campos obligatorios: "
            + ", ".join(faltantes)
        )

    grupos = [
        {
            "token": "mis_variables_numericas",
            "lexemas": "DNI, EDAD"
        },
        {
            "token": "mis_variables_texto",
            "lexemas": (
                "NOMBRE, APELLIDO, DIAGNOSTICO, EXAMENES, "
                "HOSPITAL_CLINICA, LABORATORIO, SALON, "
                "ENFERMERA_MEDICO"
            )
        },
        {
            "token": "mis_variables_fecha",
            "lexemas": "FECHA"
        },
        {
            "token": "mis_variables_hora",
            "lexemas": "HORA"
        },
        {
            "token": "mis_variables_sanguineas",
            "lexemas": "TIPO_SANGRE"
        },
        {
            "token": "separadores",
            "lexemas": ":"
        }
    ]

    expresiones = [
        {
            "lexema": campo,
            "regex": CAMPOS[campo]["regex"]
        }
        for campo in ORDEN_CAMPOS
    ]

    automatas = []

    for campo in ORDEN_CAMPOS:
        try:
            auto = compile_automata(
                CAMPOS[campo]["regex"]
            )

            auto.update({
                "campo": campo,
                "regex": CAMPOS[campo]["regex"]
            })

            automatas.append(auto)

        except Exception as exc:
            automatas.append({
                "campo": campo,
                "regex": CAMPOS[campo]["regex"],
                "error": str(exc)
            })

    sintaxis = analizar_sintaxis(texto)

    for error in sintaxis["errores_sintacticos"]:
        if error not in errores:
            errores.append(error)

    semantica = analizar_semantica(datos)

    for error in semantica["errores_semanticos"]:
        if error not in errores:
            errores.append(error)

    producciones = sintaxis["gramatica"]
    arbol = sintaxis["arbol_derivacion"]

    resultado = {
        "valido": len(errores) == 0,
        "datos": datos,
        "tokens": tokens,
        "total_tokens": len(tokens),
        "campos_reconocidos": len(campos_reconocidos),
        "total_campos": len(ORDEN_CAMPOS),
        "errores": errores,
        "grupos": grupos,
        "expresiones": expresiones,
        "automatas": automatas,
        "producciones": producciones,
        "arbol": arbol,
        "faltantes": faltantes,
        "tokens_sintacticos": sintaxis["tokens_sintacticos"],
        "errores_sintacticos": sintaxis["errores_sintacticos"],
        "pasos_sintacticos": sintaxis["pasos"],
        "estado": (
            "Registro válido"
            if not errores
            else "Registro con observaciones"
        )
    }

    resultado.update({
        "semantica": semantica["semantica"],
        "atributos_heredados": semantica["atributos_heredados"],
        "atributos_sintetizados": semantica["atributos_sintetizados"],
        "arbol_semantico": semantica["arbol_semantico"],
        "errores_semanticos": semantica["errores_semanticos"]
    })

    return resultado


# ============================================================
# RUTAS FLASK
# ============================================================

@app.route("/")
def inicio():
    return render_template("index.html")


@app.route("/analizar", methods=["POST"])
def analizar():

    payload = request.get_json(silent=True) or {}
    texto = payload.get("texto", "")

    if not isinstance(texto, str) or not texto.strip():
        return jsonify({
            "mensaje": "Ingresa un registro médico para analizar."
        }), 400

    return jsonify(analizar_registro(texto))


@app.route("/descargar-pdf", methods=["POST"])
def descargar_pdf():

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle
    )

    payload = request.get_json(silent=True) or {}
    resultado = payload.get("resultado")

    if not resultado:
        return jsonify({
            "mensaje": "Primero debes analizar un registro."
        }), 400

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()

    story = [
        Paragraph(
            "RuleCheck - Reporte de análisis",
            styles["Title"]
        ),
        Spacer(1, 10)
    ]

    story.append(
        Paragraph(
            f"<b>Estado:</b> {resultado.get('estado', '')}",
            styles["Normal"]
        )
    )

    story.append(
        Paragraph(
            f"<b>Tokens:</b> {resultado.get('total_tokens', 0)} "
            f"| <b>Campos:</b> "
            f"{resultado.get('campos_reconocidos', 0)}/"
            f"{resultado.get('total_campos', 0)}",
            styles["Normal"]
        )
    )

    story.append(Spacer(1, 10))

    story.append(
        Paragraph(
            "Agrupación de tokens y lexemas",
            styles["Heading2"]
        )
    )

    rows = [["Token (Agrupador)", "Lexemas"]]

    for grupo in resultado.get("grupos", []):
        rows.append([
            grupo["token"],
            grupo["lexemas"]
        ])

    tabla = Table(
        rows,
        colWidths=[155, 350],
        repeatRows=1
    )

    tabla.setStyle(TableStyle([
        (
            "BACKGROUND",
            (0, 0),
            (-1, 0),
            colors.HexColor("#174f7d")
        ),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), .4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP")
    ]))

    story.append(tabla)
    story.append(Spacer(1, 10))

    story.append(
        Paragraph(
            "Tokens individuales",
            styles["Heading2"]
        )
    )

    rows = [["Token", "Lexema"]]

    rows += [
        [token["token"], token["lexema"]]
        for token in resultado.get("tokens", [])
    ]

    tabla = Table(
        rows,
        colWidths=[180, 325],
        repeatRows=1
    )

    tabla.setStyle(TableStyle([
        (
            "BACKGROUND",
            (0, 0),
            (-1, 0),
            colors.HexColor("#174f7d")
        ),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), .4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP")
    ]))

    story.append(tabla)
    story.append(Spacer(1, 10))

    story.append(
        Paragraph(
            "Expresiones regulares",
            styles["Heading2"]
        )
    )

    er_rows = [
        ["Campo", "Expresión regular"]
    ]

    er_rows += [
        [x.get("lexema", ""), x.get("regex", "")]
        for x in resultado.get("expresiones", [])
    ]

    er_table = Table(
        er_rows,
        colWidths=[130, 375],
        repeatRows=1
    )

    er_table.setStyle(TableStyle([
        (
            "BACKGROUND",
            (0, 0),
            (-1, 0),
            colors.HexColor("#174f7d")
        ),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), .4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP")
    ]))

    story.append(er_table)

    for auto in resultado.get("automatas", []):

        if auto.get("error"):
            continue

        story.append(Spacer(1, 8))

        story.append(
            Paragraph(
                f"Autómatas del campo {auto.get('campo', '')}",
                styles["Heading3"]
            )
        )

        quintuple = auto.get("quintuple", {})

        q_text = (
            f"Q={quintuple.get('Q', [])} | "
            f"Sigma={quintuple.get('Sigma', [])} | "
            f"q0={quintuple.get('q0', '')} | "
            f"F={quintuple.get('F', [])}"
        )

        story.append(
            Paragraph(q_text, styles["Normal"])
        )

        tr_rows = [
            ["Estado actual", "Entrada", "Estado destino"]
        ]

        tr_rows += [
            [
                x.get("estado", ""),
                x.get("entrada", ""),
                x.get("destino", "")
            ]
            for x in auto.get("transition_table", [])
        ]

        tr_table = Table(
            tr_rows,
            colWidths=[150, 205, 150],
            repeatRows=1
        )

        tr_table.setStyle(TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#dce8f3")
            ),
            ("GRID", (0, 0), (-1, -1), .3, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("VALIGN", (0, 0), (-1, -1), "TOP")
        ]))

        story.append(tr_table)

    story.append(Spacer(1, 10))

    story.append(
        Paragraph(
            "Análisis sintáctico - Gramática libre de contexto",
            styles["Heading2"]
        )
    )

    for produccion in resultado.get("producciones", []):
        texto_seguro = (
            produccion
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

        story.append(
            Paragraph(texto_seguro, styles["Code"])
        )

    story.append(
        Paragraph(
            "Resultado sintáctico: "
            + (
                "Cadena aceptada"
                if not resultado.get("errores_sintacticos")
                else "Cadena rechazada"
            ),
            styles["Normal"]
        )
    )

    story.append(
        Paragraph(
            "Análisis semántico",
            styles["Heading2"]
        )
    )

    semantic_rows = [[
        "Campo",
        "Tipo",
        "Valor",
        "Estado"
    ]]

    for item in resultado.get("semantica", []):
        semantic_rows.append([
            item["campo"],
            item["tipo"],
            str(item["valor"]),
            item["estado"]
        ])

    semantic_table = Table(
        semantic_rows,
        repeatRows=1
    )

    semantic_table.setStyle(TableStyle([
        (
            "BACKGROUND",
            (0, 0),
            (-1, 0),
            colors.HexColor("#174f7d")
        ),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), .4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP")
    ]))

    story.append(semantic_table)

    story.append(
        Paragraph(
            "Atributos sintetizados",
            styles["Heading3"]
        )
    )

    story.append(
        Paragraph(
            str(resultado.get("atributos_sintetizados", {})),
            styles["Code"]
        )
    )

    story.append(
        Paragraph(
            "Atributos heredados",
            styles["Heading3"]
        )
    )

    story.append(
        Paragraph(
            str(resultado.get("atributos_heredados", {})),
            styles["Code"]
        )
    )

    story.append(
        Paragraph(
            "Árbol de derivación",
            styles["Heading2"]
        )
    )

    def flatten_tree(node, depth=0):
        lines = [
            ("    " * depth) + str(node.get("nombre", ""))
        ]

        for child in node.get("hijos", []):
            lines.extend(
                flatten_tree(child, depth + 1)
            )

        return lines

    for line in flatten_tree(resultado.get("arbol", {})):
        texto_seguro = (
            line
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace(" ", "&nbsp;")
        )

        story.append(
            Paragraph(texto_seguro, styles["Code"])
        )

    story.append(
        Paragraph(
            "Errores y observaciones",
            styles["Heading2"]
        )
    )

    for error in resultado.get("errores", []) or [
        "No se encontraron errores."
    ]:
        story.append(
            Paragraph(
                "• " + error,
                styles["Normal"]
            )
        )

    doc.build(story)

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="reporte_rulecheck.pdf",
        mimetype="application/pdf"
    )


if __name__ == "__main__":
    app.run(debug=True)

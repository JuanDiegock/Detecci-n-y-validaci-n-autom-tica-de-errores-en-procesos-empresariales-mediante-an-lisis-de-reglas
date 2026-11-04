import re
from collections import defaultdict, deque

# Autómatas construidos a partir de expresiones regulares de los lexemas
# del formato Campo: Valor. La validación completa de cada campo se
# realiza en run.py con sus patrones específicos.
EXPRESIONES_REGULARES = {
    "DNI": r"\d\d\d\d\d\d\d\d",
    "EDAD": r"\d|\d\d|\d\d\d",
    "DIAGNOSTICO": r"[A-Z]\d\d",
    "FECHA": r"\d\d\d\d-\d\d-\d\d",
    "HORA": r"([01]\d|2[0-3]):[0-5]\d",
    "SALON": r"(MI|CI|PED|GO)-P\d\d?-\d\d\d?",
    "TIPO_SANGRE": r"(A|B|AB|O)(\+|-)",
    "SEPARADOR": r":",
}


class ParserER:
    """Parser pequeño para ER: alternancia, concatenación, *, +, ?, () y []."""

    def __init__(self, expresion):
        self.expresion = expresion
        self.i = 0

    def actual(self):
        return self.expresion[self.i] if self.i < len(self.expresion) else None

    def parsear(self):
        arbol = self.alternativa()
        if self.i != len(self.expresion):
            raise ValueError(f"Expresión regular no válida: {self.expresion}")
        return arbol

    def alternativa(self):
        opciones = [self.concatenacion()]
        while self.actual() == "|":
            self.i += 1
            opciones.append(self.concatenacion())
        return opciones[0] if len(opciones) == 1 else ("OR", opciones)

    def concatenacion(self):
        partes = []
        while self.actual() is not None and self.actual() not in ")|":
            partes.append(self.repeticion())
        if not partes:
            return ("EPSILON",)
        return partes[0] if len(partes) == 1 else ("CONCAT", partes)

    def repeticion(self):
        nodo = self.primario()
        while self.actual() in ("*", "+", "?"):
            op = self.actual()
            self.i += 1
            nodo = {"*": ("STAR", nodo), "+": ("PLUS", nodo), "?": ("OPTIONAL", nodo)}[op]
        return nodo

    def primario(self):
        c = self.actual()
        if c is None:
            raise ValueError("Expresión regular incompleta.")
        if c == "(":
            self.i += 1
            nodo = self.alternativa()
            if self.actual() != ")":
                raise ValueError("Falta cerrar un paréntesis.")
            self.i += 1
            return nodo
        if c == "[":
            return self.clase_caracteres()
        if c == "\\":
            self.i += 1
            c = self.actual()
            if c is None:
                raise ValueError("Escape incompleto.")
            self.i += 1
            if c == "d":
                return ("CLASS", tuple("0123456789"))
            if c == "s":
                return ("CLASS", (" ", "\t"))
            return ("LITERAL", c)
        if c in "*+?)":
            raise ValueError(f"Operador inesperado: {c}")
        self.i += 1
        if c == ".":
            return ("CLASS", tuple(
                "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                "0123456789 áéíóúÁÉÍÓÚñÑ.,'-/:+"
            ))
        return ("LITERAL", c)

    def clase_caracteres(self):
        self.i += 1
        chars = []
        while self.actual() is not None and self.actual() != "]":
            first = self.actual()
            self.i += 1
            if (self.actual() == "-" and self.i + 1 < len(self.expresion)
                    and self.expresion[self.i + 1] != "]"):
                self.i += 1
                last = self.actual()
                self.i += 1
                if ord(first) > ord(last):
                    raise ValueError("Rango inválido.")
                chars.extend(chr(n) for n in range(ord(first), ord(last) + 1))
            else:
                chars.append(first)
        if self.actual() != "]":
            raise ValueError("Falta cerrar una clase.")
        self.i += 1
        return ("CLASS", tuple(dict.fromkeys(chars)))


class ConstructorAFND:
    def __init__(self):
        self.estados = []
        self.transiciones = []

    def nuevo(self):
        estado = f"q{len(self.estados)}"
        self.estados.append(estado)
        return estado

    def conectar(self, origen, simbolo, destino):
        self.transiciones.append({
            "origen": origen, "simbolo": simbolo, "destino": destino
        })

    def construir(self, nodo):
        tipo = nodo[0]
        if tipo == "LITERAL":
            a, b = self.nuevo(), self.nuevo()
            self.conectar(a, nodo[1], b)
            return a, b
        if tipo == "CLASS":
            a, b = self.nuevo(), self.nuevo()
            for c in nodo[1]:
                self.conectar(a, c, b)
            return a, b
        if tipo == "EPSILON":
            a, b = self.nuevo(), self.nuevo()
            self.conectar(a, "ε", b)
            return a, b
        if tipo == "CONCAT":
            fragments = [self.construir(n) for n in nodo[1]]
            for (_, end), (start, _) in zip(fragments, fragments[1:]):
                self.conectar(end, "ε", start)
            return fragments[0][0], fragments[-1][1]
        if tipo == "OR":
            a, b = self.nuevo(), self.nuevo()
            for option in nodo[1]:
                start, end = self.construir(option)
                self.conectar(a, "ε", start)
                self.conectar(end, "ε", b)
            return a, b
        if tipo in ("STAR", "PLUS", "OPTIONAL"):
            a, b = self.nuevo(), self.nuevo()
            start, end = self.construir(nodo[1])
            self.conectar(a, "ε", start)
            self.conectar(end, "ε", b)
            if tipo in ("STAR", "OPTIONAL"):
                self.conectar(a, "ε", b)
            if tipo in ("STAR", "PLUS"):
                self.conectar(end, "ε", start)
            return a, b
        raise ValueError(f"Nodo desconocido: {tipo}")


def crear_afnd(tipo, expresion):
    constructor = ConstructorAFND()
    inicial, final = constructor.construir(ParserER(expresion).parsear())
    alfabeto = sorted({
        t["simbolo"] for t in constructor.transiciones if t["simbolo"] != "ε"
    })
    return {
        "tipo": tipo, "estados": constructor.estados,
        "alfabeto": alfabeto, "inicial": inicial, "finales": [final],
        "transiciones": constructor.transiciones
    }


def convertir_a_afd(afnd):
    trans = defaultdict(list)
    for t in afnd["transiciones"]:
        trans[(t["origen"], t["simbolo"])].append(t["destino"])

    def cierre(estados):
        resultado = set(estados)
        pila = list(estados)
        while pila:
            estado = pila.pop()
            for destino in trans[(estado, "ε")]:
                if destino not in resultado:
                    resultado.add(destino)
                    pila.append(destino)
        return frozenset(resultado)

    inicial = cierre([afnd["inicial"]])
    conjuntos = [inicial]
    pendientes = deque([inicial])
    transiciones = []
    alfabeto = afnd["alfabeto"]

    while pendientes:
        actual = pendientes.popleft()
        for simbolo in alfabeto:
            destinos = set()
            for estado in actual:
                destinos.update(trans[(estado, simbolo)])
            nuevo = cierre(destinos)
            if nuevo not in conjuntos:
                conjuntos.append(nuevo)
                pendientes.append(nuevo)
            transiciones.append((actual, simbolo, nuevo))

    nombres = {c: f"D{i}" for i, c in enumerate(conjuntos)}
    tabla = [
        {"origen": nombres[a], "simbolo": s, "destino": nombres[b]}
        for a, s, b in transiciones
    ]
    finales_afnd = set(afnd["finales"])
    finales = [nombres[c] for c in conjuntos if set(c) & finales_afnd]

    return {
        "tipo": afnd["tipo"],
        "estados": [nombres[c] for c in conjuntos],
        "alfabeto": alfabeto,
        "inicial": nombres[inicial],
        "finales": finales,
        "transiciones": tabla,
        "subconjuntos": {nombres[c]: sorted(c) for c in conjuntos}
    }


def generar_quintupla(automata):
    return {
        "Q": automata["estados"],
        "Sigma": automata["alfabeto"],
        "delta": automata["transiciones"],
        "q0": automata["inicial"],
        "F": automata["finales"]
    }


def generar_automatas():
    resultados = []
    for tipo, expresion in EXPRESIONES_REGULARES.items():
        afnd = crear_afnd(tipo, expresion)
        afd = convertir_a_afd(afnd)
        resultados.append({
            "tipo": tipo,
            "expresion_regular": expresion,
            "afnd": afnd,
            "quintupla_afnd": generar_quintupla(afnd),
            "afd": afd,
            "quintupla_afd": generar_quintupla(afd)
        })
    return resultados


def generar_expresiones_regulares():
    ejemplos = {
        "DNI": "12345678",
        "EDAD": "30",
        "DIAGNOSTICO": "J00",
        "FECHA": "2025-06-10",
        "HORA": "09:15",
        "SALON": "MI-P2-103",
        "TIPO_SANGRE": "A+",
        "SEPARADOR": ":",
    }
    descripciones = {
        "DNI": "Documento de identidad (8 dígitos)",
        "EDAD": "Edad expresada de 1 a 3 dígitos",
        "DIAGNOSTICO": "Código de diagnóstico: una letra y dos dígitos",
        "FECHA": "Fecha en formato AAAA-MM-DD",
        "HORA": "Hora en formato HH:MM",
        "SALON": "Código de salón",
        "TIPO_SANGRE": "Grupo sanguíneo ABO/Rh",
        "SEPARADOR": "Separador entre campo y valor",
    }
    return [
        {
            "tipo": tipo,
            "expresion": expresion,
            "descripcion": descripciones[tipo],
            "ejemplo": ejemplos[tipo]
        }
        for tipo, expresion in EXPRESIONES_REGULARES.items()
    ]


def identificar_lexema(lexema):
    for tipo, expresion in EXPRESIONES_REGULARES.items():
        if re.fullmatch(expresion, lexema):
            return tipo
    return "NO_RECONOCIDO"

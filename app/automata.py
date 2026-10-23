
import re
from collections import defaultdict, deque

# ============================================================
# 5. EXPRESIONES REGULARES
# ============================================================

EXPRESIONES_REGULARES = {
    "PALABRA_RESERVADA": r"REGLA|SI|ENTONCES|Y|O|NO|APROBAR|RECHAZAR",
    "IDENTIFICADOR": r"[a-zA-Z_][a-zA-Z0-9_]*",
    "NUMERO": r"[0-9]+(\.[0-9]+)?",
    "OPERADOR": r">=|<=|==|!=|>|<|=|\+|-|\*|/",
    "DELIMITADOR": r"[\(\):;,.]"
}


# ============================================================
# PARSER DE EXPRESIONES REGULARES
# Admite: |, *, +, ?, (), clases [] y rangos.
# ============================================================

class ParserER:
    def __init__(self, expresion):
        self.expresion = expresion
        self.i = 0

    def parsear(self):
        resultado = self.alternativa()
        if self.i != len(self.expresion):
            raise ValueError(
                f"Expresión regular no válida: {self.expresion}"
            )
        return resultado

    def alternativa(self):
        opciones = [self.concatenacion()]
        while self.actual() == "|":
            self.i += 1
            opciones.append(self.concatenacion())
        if len(opciones) == 1:
            return opciones[0]
        return ("OR", opciones)

    def concatenacion(self):
        partes = []
        while self.actual() is not None and self.actual() not in ")|":
            partes.append(self.repeticion())
        if not partes:
            return ("EPSILON",)
        if len(partes) == 1:
            return partes[0]
        return ("CONCAT", partes)

    def repeticion(self):
        nodo = self.primario()
        while self.actual() in ("*", "+", "?"):
            operador = self.actual()
            self.i += 1
            nodo = {
                "*": ("STAR", nodo),
                "+": ("PLUS", nodo),
                "?": ("OPTIONAL", nodo)
            }[operador]
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
            if self.actual() is None:
                raise ValueError("Escape incompleto.")
            c = self.actual()
            self.i += 1

            if c == "d":
                return ("CLASS", tuple("0123456789"))
            if c == "w":
                return ("CLASS", tuple(
                    "abcdefghijklmnopqrstuvwxyz"
                    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                    "0123456789_"
                ))
            if c == "s":
                return ("CLASS", (" ", "\t"))
            return ("LITERAL", c)

        if c in "*+?)":
            raise ValueError(f"Operador inesperado: {c}")

        self.i += 1
        if c == ".":
            return ("CLASS", tuple(
                "abcdefghijklmnopqrstuvwxyz"
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                "0123456789_"
                " .,:;()><=!+-*/\t"
            ))
        return ("LITERAL", c)

    def clase_caracteres(self):
        self.i += 1
        caracteres = []

        while self.actual() is not None and self.actual() != "]":
            primero = self.actual()
            self.i += 1

            if (
                self.actual() == "-"
                and self.i + 1 < len(self.expresion)
                and self.expresion[self.i + 1] != "]"
            ):
                self.i += 1
                ultimo = self.actual()
                self.i += 1
                if ord(primero) > ord(ultimo):
                    raise ValueError("Rango inválido en clase.")
                caracteres.extend(
                    chr(n) for n in range(ord(primero), ord(ultimo) + 1)
                )
            else:
                caracteres.append(primero)

        if self.actual() != "]":
            raise ValueError("Falta cerrar una clase de caracteres.")

        self.i += 1
        return ("CLASS", tuple(dict.fromkeys(caracteres)))

    def actual(self):
        if self.i >= len(self.expresion):
            return None
        return self.expresion[self.i]


# ============================================================
# 5. CONSTRUCCIÓN DEL AFND POR THOMPSON
# ============================================================

class ConstructorAFND:
    def __init__(self, tipo):
        self.tipo = tipo
        self.contador = 0
        self.estados = []
        self.transiciones = []

    def nuevo_estado(self):
        estado = f"q{self.contador}"
        self.contador += 1
        self.estados.append(estado)
        return estado

    def conectar(self, origen, simbolo, destino):
        self.transiciones.append({
            "origen": origen,
            "simbolo": simbolo,
            "destino": destino
        })

    def construir(self, nodo):
        tipo = nodo[0]

        if tipo == "LITERAL":
            inicio = self.nuevo_estado()
            fin = self.nuevo_estado()
            self.conectar(inicio, nodo[1], fin)
            return inicio, fin

        if tipo == "CLASS":
            inicio = self.nuevo_estado()
            fin = self.nuevo_estado()
            for simbolo in nodo[1]:
                self.conectar(inicio, simbolo, fin)
            return inicio, fin

        if tipo == "EPSILON":
            inicio = self.nuevo_estado()
            fin = self.nuevo_estado()
            self.conectar(inicio, "ε", fin)
            return inicio, fin

        if tipo == "CONCAT":
            fragmentos = [self.construir(n) for n in nodo[1]]
            for (_, fin), (inicio_siguiente, _) in zip(
                fragmentos, fragmentos[1:]
            ):
                self.conectar(fin, "ε", inicio_siguiente)
            return fragmentos[0][0], fragmentos[-1][1]

        if tipo == "OR":
            inicio = self.nuevo_estado()
            fin = self.nuevo_estado()
            for opcion in nodo[1]:
                sub_inicio, sub_fin = self.construir(opcion)
                self.conectar(inicio, "ε", sub_inicio)
                self.conectar(sub_fin, "ε", fin)
            return inicio, fin

        if tipo == "STAR":
            inicio = self.nuevo_estado()
            fin = self.nuevo_estado()
            sub_inicio, sub_fin = self.construir(nodo[1])
            self.conectar(inicio, "ε", fin)
            self.conectar(inicio, "ε", sub_inicio)
            self.conectar(sub_fin, "ε", sub_inicio)
            self.conectar(sub_fin, "ε", fin)
            return inicio, fin

        if tipo == "PLUS":
            inicio = self.nuevo_estado()
            fin = self.nuevo_estado()
            sub_inicio, sub_fin = self.construir(nodo[1])
            self.conectar(inicio, "ε", sub_inicio)
            self.conectar(sub_fin, "ε", sub_inicio)
            self.conectar(sub_fin, "ε", fin)
            return inicio, fin

        if tipo == "OPTIONAL":
            inicio = self.nuevo_estado()
            fin = self.nuevo_estado()
            sub_inicio, sub_fin = self.construir(nodo[1])
            self.conectar(inicio, "ε", sub_inicio)
            self.conectar(inicio, "ε", fin)
            self.conectar(sub_fin, "ε", fin)
            return inicio, fin

        raise ValueError(f"Tipo de nodo desconocido: {tipo}")


def crear_afnd(tipo, expresion):
    arbol = ParserER(expresion).parsear()
    constructor = ConstructorAFND(tipo)
    inicial, final = constructor.construir(arbol)

    alfabeto = sorted({
        t["simbolo"]
        for t in constructor.transiciones
        if t["simbolo"] != "ε"
    })

    return {
        "tipo": tipo,
        "estados": constructor.estados,
        "alfabeto": alfabeto,
        "inicial": inicial,
        "finales": [final],
        "transiciones": constructor.transiciones
    }


# ============================================================
# 6. CONVERSIÓN DEL AFND AL AFD
# Construcción por subconjuntos con cierre-ε.
# ============================================================

def convertir_a_afd(afnd):
    transiciones = defaultdict(list)

    for t in afnd["transiciones"]:
        transiciones[(t["origen"], t["simbolo"])].append(t["destino"])

    alfabeto = afnd["alfabeto"]
    finales_afnd = set(afnd["finales"])

    def cierre_epsilon(estados):
        resultado = set(estados)
        pendientes = list(estados)

        while pendientes:
            estado = pendientes.pop()
            for destino in transiciones[(estado, "ε")]:
                if destino not in resultado:
                    resultado.add(destino)
                    pendientes.append(destino)

        return frozenset(resultado)

    inicial = cierre_epsilon([afnd["inicial"]])
    conjuntos = [inicial]
    pendientes = deque([inicial])
    transiciones_afd = []

    while pendientes:
        actual = pendientes.popleft()

        for simbolo in alfabeto:
            destinos = set()

            for estado in actual:
                destinos.update(transiciones[(estado, simbolo)])

            nuevo = cierre_epsilon(destinos)

            if nuevo not in conjuntos:
                conjuntos.append(nuevo)
                pendientes.append(nuevo)

            transiciones_afd.append({
                "origen_conjunto": actual,
                "simbolo": simbolo,
                "destino_conjunto": nuevo
            })

    nombres = {
        conjunto: f"D{i}"
        for i, conjunto in enumerate(conjuntos)
    }

    tabla_transiciones = [
        {
            "origen": nombres[t["origen_conjunto"]],
            "simbolo": t["simbolo"],
            "destino": nombres[t["destino_conjunto"]]
        }
        for t in transiciones_afd
    ]

    finales = [
        nombres[conjunto]
        for conjunto in conjuntos
        if set(conjunto) & finales_afnd
    ]

    return {
        "tipo": afnd["tipo"],
        "estados": [nombres[c] for c in conjuntos],
        "alfabeto": alfabeto,
        "inicial": nombres[inicial],
        "finales": finales,
        "transiciones": tabla_transiciones,
        "tabla_completa": [
            {
                "estado": nombres[c],
                **{
                    simbolo: next(
                        t["destino"]
                        for t in tabla_transiciones
                        if t["origen"] == nombres[c]
                        and t["simbolo"] == simbolo
                    )
                    for simbolo in alfabeto
                }
            }
            for c in conjuntos
        ],
        "subconjuntos": {
            nombres[c]: sorted(c)
            for c in conjuntos
        }
    }


# ============================================================
# QUÍNTUPLA FORMAL
# M = (Q, Σ, δ, q0, F)
# ============================================================

def generar_quintupla(automata):
    return {
        "Q": automata["estados"],
        "Sigma": automata["alfabeto"],
        "delta": automata["transiciones"],
        "q0": automata["inicial"],
        "F": automata["finales"]
    }


# ============================================================
# GENERACIÓN DE LOS CINCO AUTÓMATAS
# ============================================================

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
    return [
        {"tipo": tipo, "expresion": expresion}
        for tipo, expresion in EXPRESIONES_REGULARES.items()
    ]


def identificar_lexema(lexema):
    for tipo, expresion in EXPRESIONES_REGULARES.items():
        if re.fullmatch(expresion, lexema):
            return tipo
    return "NO_RECONOCIDO"

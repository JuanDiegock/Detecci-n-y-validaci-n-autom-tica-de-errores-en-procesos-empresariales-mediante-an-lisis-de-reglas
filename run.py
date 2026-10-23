
from pathlib import Path
from flask import Flask, render_template, request, jsonify
import re

BASE_DIR = Path(__file__).resolve().parent


def buscar_archivo(nombre):
    """Busca un archivo dentro del proyecto, incluidas sus subcarpetas."""
    encontrados = []

    for ruta in BASE_DIR.rglob(nombre):
        if any(
            parte in {".venv", "venv", "__pycache__", ".git"}
            for parte in ruta.parts
        ):
            continue

        encontrados.append(ruta)

    return encontrados


# Buscar los archivos reales
htmls = buscar_archivo("index.html")
csss = buscar_archivo("styles.css")
jss = buscar_archivo("app.js")

print("\n========== DIAGNÓSTICO RULECHECK ==========")
print("Run.py:", BASE_DIR)
print("HTML encontrados:", htmls)
print("CSS encontrados:", csss)
print("JS encontrados:", jss)
print("===========================================\n")

if not htmls:
    raise FileNotFoundError(
        "No existe ningún index.html dentro del proyecto. "
        "Comprueba que el archivo esté guardado en VS Code."
    )

# Usa la carpeta real donde se encontró index.html
TEMPLATE_DIR = htmls[0].parent

# Prioriza la carpeta que contiene los dos archivos estáticos
STATIC_DIR = BASE_DIR / "app" / "static"

if not (STATIC_DIR / "styles.css").is_file() or not (
    STATIC_DIR / "app.js"
).is_file():
    if csss and jss and csss[0].parent == jss[0].parent:
        STATIC_DIR = csss[0].parent
    elif csss:
        STATIC_DIR = csss[0].parent
    elif jss:
        STATIC_DIR = jss[0].parent

app = Flask(
    __name__,
    template_folder=str(TEMPLATE_DIR),
    static_folder=str(STATIC_DIR)
)


# =====================================================
# TOKENS Y LEXEMAS
# =====================================================

PATRON_TOKEN = re.compile(
    r"REGLA|SI|ENTONCES|APROBAR|RECHAZAR|Y|O|NO"
    r"|[a-zA-Z_][a-zA-Z0-9_]*"
    r"|\d+(?:\.\d+)?"
    r"|>=|<=|==|!="
    r"|[><=+\-*/]"
    r"|[():;,.]",
    re.IGNORECASE
)

RESERVADAS = {
    "REGLA", "SI", "ENTONCES", "APROBAR",
    "RECHAZAR", "Y", "O", "NO"
}


def analizar_tokens(codigo):
    tokens = []
    errores = []

    for num_linea, linea in enumerate(codigo.splitlines(), 1):
        posicion = 0

        for coincidencia in PATRON_TOKEN.finditer(linea):
            ignorado = linea[posicion:coincidencia.start()]

            if ignorado.strip():
                errores.append({
                    "posicion": num_linea,
                    "mensaje": f"Símbolo no reconocido: {ignorado.strip()}"
                })

            lexema = coincidencia.group()

            if lexema.upper() in RESERVADAS:
                tipo = "PALABRA_RESERVADA"
            elif lexema[0].isdigit():
                tipo = "NUMERO"
            elif re.fullmatch(r"[><=+\-*/]+|>=|<=|==|!=", lexema):
                tipo = "OPERADOR"
            elif lexema in {"(", ")", ":", ";", ",", "."}:
                tipo = "DELIMITADOR"
            else:
                tipo = "IDENTIFICADOR"

            tokens.append({
                "token": tipo,
                "lexema": lexema,
                "posicion": f"{num_linea}:{coincidencia.start() + 1}"
            })

            posicion = coincidencia.end()

        sobrante = linea[posicion:]

        if sobrante.strip():
            errores.append({
                "posicion": num_linea,
                "mensaje": f"Símbolo no reconocido: {sobrante.strip()}"
            })

    return tokens, errores


# =====================================================
# EXPRESIÓN REGULAR Y VALIDACIÓN
# =====================================================

EXPRESIONES = {
    "PALABRA_RESERVADA": r"REGLA|SI|ENTONCES|Y|O|NO|APROBAR|RECHAZAR",
    "IDENTIFICADOR": r"[a-zA-Z_][a-zA-Z0-9_]*",
    "NUMERO": r"[0-9]+(\.[0-9]+)?",
    "OPERADOR": r">=|<=|==|!=|>|<|=|\+|-|\*|/",
    "DELIMITADOR": r"[\(\):;,.]"
}

ER_REGLA = re.compile(
    r"^\s*REGLA\s+[a-zA-Z_][a-zA-Z0-9_]*"
    r"\s+SI\s+[a-zA-Z_][a-zA-Z0-9_]*"
    r"\s*(?:>=|<=|==|!=|>|<)\s*\d+(?:\.\d+)?"
    r"\s+ENTONCES\s+(?:APROBAR|RECHAZAR)\s*$",
    re.IGNORECASE
)


def validar_reglas(codigo):
    reglas = []
    errores = []

    for numero, original in enumerate(codigo.splitlines(), 1):
        linea = original.strip()

        if not linea:
            continue

        valida = bool(ER_REGLA.fullmatch(linea))

        reglas.append({
            "linea": numero,
            "regla": linea,
            "coincide": valida
        })

        if not valida:
            errores.append({
                "posicion": numero,
                "mensaje": "La regla no cumple la estructura esperada."
            })

    return reglas, errores


# =====================================================
# AUTÓMATAS POR CATEGORÍA
# =====================================================

def generar_automatas():
    resultados = []

    patrones = {
        "PALABRA_RESERVADA": [
            "REGLA", "SI", "ENTONCES", "Y",
            "O", "NO", "APROBAR", "RECHAZAR"
        ],
        "IDENTIFICADOR": ["LETRA", "LETRA_O_DIGITO"],
        "NUMERO": ["DIGITO", "DIGITO"],
        "OPERADOR": [">=", "<=", "==", "!=", ">", "<", "=", "+", "-", "*", "/"],
        "DELIMITADOR": ["(", ")", ":", ";", ",", "."]
    }

    for tipo, er in EXPRESIONES.items():
        estados = ["q0"]
        transiciones = []
        finales = []
        contador = 1

        for alternativa in patrones[tipo]:
            actual = "q0"
            destino = f"q{contador}"
            contador += 1

            estados.append(destino)
            transiciones.append({
                "origen": actual,
                "simbolo": alternativa,
                "destino": destino
            })
            finales.append(destino)

        afnd = {
            "tipo": tipo,
            "estados": estados,
            "alfabeto": sorted(set(t["simbolo"] for t in transiciones)),
            "inicial": "q0",
            "finales": finales,
            "transiciones": transiciones
        }

        afd = {
            "tipo": tipo,
            "estados": estados,
            "alfabeto": afnd["alfabeto"],
            "inicial": "q0",
            "finales": finales,
            "transiciones": transiciones
        }

        resultados.append({
            "tipo": tipo,
            "expresion_regular": er,
            "afnd": afnd,
            "quintupla_afnd": {
                "Q": afnd["estados"],
                "Sigma": afnd["alfabeto"],
                "q0": afnd["inicial"],
                "F": afnd["finales"],
                "Delta": afnd["transiciones"]
            },
            "afd": afd,
            "quintupla_afd": {
                "Q": afd["estados"],
                "Sigma": afd["alfabeto"],
                "q0": afd["inicial"],
                "F": afd["finales"],
                "Delta": afd["transiciones"]
            }
        })

    return resultados


# =====================================================
# RUTAS
# =====================================================

@app.route("/")
def inicio():
    return render_template("index.html")


@app.route("/analizar", methods=["POST"])
def analizar():
    datos = request.get_json(silent=True) or {}
    codigo = datos.get("codigo", "")

    if not isinstance(codigo, str):
        return jsonify({"error": "El contenido no es válido."}), 400

    tokens, errores_lexicos = analizar_tokens(codigo)
    reglas, errores_reglas = validar_reglas(codigo)
    errores = errores_lexicos + errores_reglas

    return jsonify({
        "tokens": tokens,
        "errores": errores,
        "valido": not errores,
        "expresiones": [
            {"tipo": tipo, "expresion": er}
            for tipo, er in EXPRESIONES.items()
        ],
        "reglas": reglas,
        "automatas": generar_automatas()
    })


@app.route("/subir", methods=["POST"])
def subir():
    archivo = request.files.get("archivo")

    if not archivo or not archivo.filename:
        return jsonify({"error": "Selecciona un archivo."}), 400

    try:
        codigo = archivo.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return jsonify({"error": "El archivo debe estar en UTF-8."}), 400

    return jsonify({"codigo": codigo})


if __name__ == "__main__":
    app.run(debug=True)

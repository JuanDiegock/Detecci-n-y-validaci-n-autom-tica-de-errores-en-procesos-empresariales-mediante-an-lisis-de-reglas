from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import re

from app.automata import generar_automatas, generar_expresiones_regulares


BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, template_folder="templates", static_folder="static")


# ==========================================
# 1. CAMPOS DEL REGISTRO MÉDICO
# ==========================================

CAMPOS = [
    "Nombre",
    "Apellido",
    "DNI",
    "Edad",
    "Diagnostico",
    "Fecha",
    "Hora",
    "Hospital/Clinica",
    "Laboratorio",
    "Salon",
    "Examenes",
    "Enfermera/Medico",
    "Tipo de sangre",
]


EJEMPLO = """Nombre: Juan
Apellido: Perez
DNI: 12345678
Edad: 30
Diagnostico: J00
Fecha: 2025-06-10
Hora: 09:15
Hospital/Clinica: Clinica Central
Laboratorio: Lab Uno
Salon: MI-P2-103
Examenes: Hemograma
Enfermera/Medico: Dra Lopez
Tipo de sangre: A+"""


# ==========================================
# 2. EXPRESIONES REGULARES
# ==========================================

PATRONES = {
    "Nombre": r"[A-Za-zÁÉÍÓÚáéíóúÜüÑñ ]{2,60}",
    "Apellido": r"[A-Za-zÁÉÍÓÚáéíóúÜüÑñ ]{2,60}",
    "DNI": r"\d{8}",
    "Edad": r"\d{1,3}",
    "Diagnostico": r"[A-Z]\d{2}",
    "Fecha": r"\d{4}-\d{2}-\d{2}",
    "Hora": r"(?:[01]\d|2[0-3]):[0-5]\d",
    "Hospital/Clinica": r"[A-Za-zÁÉÍÓÚáéíóúÜüÑñ0-9 .'-]{2,80}",
    "Laboratorio": r"[A-Za-zÁÉÍÓÚáéíóúÜüÑñ0-9 .'-]{2,60}",
    "Salon": r"(?:MI|CI|PED|GO)-P\d{1,2}-\d{1,3}",
    "Examenes": r"[A-Za-zÁÉÍÓÚáéíóúÜüÑñ0-9 .,'-]{2,80}",
    "Enfermera/Medico": r"[A-Za-zÁÉÍÓÚáéíóúÜüÑñ .'-]{2,60}",
    "Tipo de sangre": r"(?:A|B|AB|O)[+-]",
}


DESCRIPCIONES_CAMPOS = {
    "Nombre": ("Nombre del paciente", "Juan", "id_nombre"),
    "Apellido": ("Apellido del paciente", "Perez", "id_apellido"),
    "DNI": ("Documento de identidad de 8 dígitos", "12345678", "id_dni"),
    "Edad": ("Edad del paciente (1 a 3 dígitos)", "30", "id_edad"),
    "Diagnostico": ("Código de diagnóstico", "J00", "id_diagnostico"),
    "Fecha": ("Fecha en formato AAAA-MM-DD", "2025-06-10", "id_fecha"),
    "Hora": ("Hora en formato HH:MM", "09:15", "id_hora"),
    "Hospital/Clinica": ("Nombre del hospital o clínica", "Clinica Central", "id_hospital"),
    "Laboratorio": ("Nombre del laboratorio", "Lab Uno", "id_laboratorio"),
    "Salon": ("Código de salón", "MI-P2-103", "id_salon"),
    "Examenes": ("Nombre del examen médico", "Hemograma", "id_examenes"),
    "Enfermera/Medico": ("Nombre del personal médico", "Dra Lopez", "id_personal"),
    "Tipo de sangre": ("Grupo sanguíneo ABO y Rh", "A+", "id_tipo_sangre"),
}


# ==========================================
# 3. NORMALIZACIÓN DE CAMPOS
# ==========================================

def normalizar(texto):
    return texto.strip().casefold()


def obtener_campos():
    campos = {normalizar(c): c for c in CAMPOS}

    # Nombres utilizados en el lenguaje DSL.
    campos.update({
        "hospital_clinica": "Hospital/Clinica",
        "enfermera_medico": "Enfermera/Medico",
        "tipo_sangre": "Tipo de sangre",
    })

    return campos


# ==========================================
# 4. ANÁLISIS LÉXICO
# ==========================================

def analizar_lexico(codigo):
    tokens = []
    errores = []
    campos_por_nombre = obtener_campos()

    for numero, linea in enumerate(codigo.splitlines(), 1):

        if not linea.strip():
            continue

        if ":" not in linea:
            errores.append({
                "posicion": numero,
                "mensaje": "Falta el separador ':' entre el campo y su valor."
            })

            tokens.append({
                "token": "LINEA_INVALIDA",
                "lexema": linea.strip(),
                "posicion": f"{numero}:1",
                "descripcion": "Línea sin separador campo-valor",
                "ejemplo": "Nombre: Juan"
            })

            continue

        campo_original, valor_original = linea.split(":", 1)

        campo = campos_por_nombre.get(normalizar(campo_original))
        valor = valor_original.strip()

        columna_valor = len(campo_original) + 2

        if campo is None:
            errores.append({
                "posicion": numero,
                "mensaje": f"Campo no reconocido: {campo_original.strip()}."
            })

            tipo_campo = "CAMPO_NO_RECONOCIDO"
            descripcion = "Campo que no pertenece al formato establecido"
            ejemplo = "Nombre"

        else:
            descripcion, ejemplo, tipo_campo = DESCRIPCIONES_CAMPOS[campo]

        tokens.append({
            "token": tipo_campo,
            "lexema": campo_original.strip(),
            "posicion": f"{numero}:1",
            "descripcion": descripcion,
            "ejemplo": campo
        })

        tokens.append({
            "token": "SEPARADOR",
            "lexema": ":",
            "posicion": f"{numero}:{len(campo_original) + 1}",
            "descripcion": "Dos puntos: separa el nombre del campo de su valor",
            "ejemplo": ":"
        })

        tokens.append({
            "token": "VALOR_" + (campo or "DESCONOCIDO").upper().replace("/", "_").replace(" ", "_"),
            "lexema": valor,
            "posicion": f"{numero}:{columna_valor}",
            "descripcion": f"Valor correspondiente al campo {campo}" if campo else "Valor de un campo desconocido",
            "ejemplo": ejemplo if campo else "—"
        })

    return tokens, errores


# ==========================================
# 5. VALIDACIÓN SINTÁCTICA Y DE CAMPOS
# ==========================================

def validar_registro(codigo):
    reglas = []
    errores = []
    encontrados = {}

    campos_por_nombre = obtener_campos()

    for numero, original in enumerate(codigo.splitlines(), 1):

        linea = original.strip()

        if not linea:
            continue

        if ":" not in linea:
            mensaje = "Formato esperado: Campo: Valor"

            errores.append({
                "posicion": numero,
                "mensaje": mensaje
            })

            reglas.append({
                "linea": numero,
                "regla": linea,
                "coincide": False,
                "detalle": mensaje
            })

            continue

        campo_original, valor = linea.split(":", 1)

        campo = campos_por_nombre.get(normalizar(campo_original))
        valor = valor.strip()

        if not campo:
            mensaje = f"Campo no reconocido: {campo_original.strip()}."

            errores.append({
                "posicion": numero,
                "mensaje": mensaje
            })

            reglas.append({
                "linea": numero,
                "regla": linea,
                "coincide": False,
                "detalle": mensaje
            })

            continue

        clave = normalizar(campo)

        if clave in encontrados:
            mensaje = f"El campo '{campo}' está duplicado."

            errores.append({
                "posicion": numero,
                "mensaje": mensaje
            })

            reglas.append({
                "linea": numero,
                "regla": linea,
                "coincide": False,
                "detalle": mensaje
            })

            continue

        encontrados[clave] = (numero, valor)

        patron = PATRONES[campo]
        valido = bool(re.fullmatch(patron, valor))

        # Comprobar que la fecha exista realmente.
        if valido and campo == "Fecha":
            try:
                datetime.strptime(valor, "%Y-%m-%d")
            except ValueError:
                valido = False

        if valido:
            detalle = "Formato correcto."

        else:
            detalle = f"Valor inválido para {campo}. Verifica el formato esperado."

            errores.append({
                "posicion": numero,
                "mensaje": detalle
            })

        reglas.append({
            "linea": numero,
            "regla": linea,
            "coincide": valido,
            "detalle": detalle
        })

    # Comprobar campos obligatorios que no se hayan ingresado.
    for campo in CAMPOS:

        if normalizar(campo) not in encontrados:

            mensaje = f"Falta el campo obligatorio: {campo}."

            errores.append({
                "posicion": "—",
                "mensaje": mensaje
            })

            reglas.append({
                "linea": "—",
                "regla": campo,
                "coincide": False,
                "detalle": "Campo obligatorio ausente."
            })

    return reglas, errores


# ==========================================
# 6. PÁGINA PRINCIPAL
# ==========================================

@app.route("/")
def inicio():
    return render_template("index.html", ejemplo=EJEMPLO)


# ==========================================
# 7. ANALIZAR Y VALIDAR REGISTRO
# ==========================================

@app.route("/analizar", methods=["POST"])
def analizar():

    datos = request.get_json(silent=True) or {}
    codigo = datos.get("codigo", "")

    if not isinstance(codigo, str):
        return jsonify({
            "error": "El contenido enviado no es válido."
        }), 400

    lineas_procesables = []

    for linea in codigo.splitlines():

        limpia = linea.strip()

        # Ignorar encabezado y llave de cierre del DSL.
        if not limpia:
            continue

        if re.fullmatch(
            r"REGISTRO_MEDICO\s*\{",
            limpia,
            re.IGNORECASE
        ):
            continue

        if limpia == "}":
            continue

        lineas_procesables.append(linea)

    # Unir las líneas con saltos de línea reales.
    codigo_normalizado = "\n".join(lineas_procesables)

    # Ejecutar análisis léxico y validación.
    tokens, errores_lexicos = analizar_lexico(codigo_normalizado)

    reglas, errores_validacion = validar_registro(codigo_normalizado)

    errores = errores_lexicos + errores_validacion

    return jsonify({
        "tokens": tokens,
        "errores": errores,
        "valido": not errores,
        "expresiones": generar_expresiones_regulares(),
        "reglas": reglas,
        "automatas": generar_automatas(),
        "campos_obligatorios": CAMPOS,
        "total_campos": len(CAMPOS)
    })


# ==========================================
# 8. CARGAR ARCHIVO TXT
# ==========================================

@app.route("/subir", methods=["POST"])
def subir():

    archivo = request.files.get("archivo")

    if not archivo or not archivo.filename:
        return jsonify({
            "error": "Selecciona un archivo .txt."
        }), 400

    if not archivo.filename.lower().endswith(".txt"):
        return jsonify({
            "error": "Solo se permiten archivos .txt."
        }), 400

    try:
        codigo = archivo.read().decode("utf-8-sig")

    except UnicodeDecodeError:
        return jsonify({
            "error": "El archivo debe estar guardado en UTF-8."
        }), 400

    return jsonify({
        "codigo": codigo
    })


# ==========================================
# 9. INICIAR APLICACIÓN
# ==========================================

if __name__ == "__main__":
    app.run(debug=True)

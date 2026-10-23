
const editor = document.getElementById("codigo");
const archivo = document.getElementById("archivo");
const botonAnalizar = document.getElementById("analizar");
const mensaje = document.getElementById("mensaje");

document.getElementById("ejemplo").addEventListener("click", () => {
    editor.value =
        "REGLA validar_compra SI monto > 0 ENTONCES APROBAR\n" +
        "REGLA validar_pago SI monto < 0 ENTONCES RECHAZAR";
    mensaje.textContent = "Ejemplo cargado.";
});

archivo.addEventListener("change", async () => {
    if (!archivo.files.length) return;
    const datos = new FormData();
    datos.append("archivo", archivo.files[0]);

    try {
        const respuesta = await fetch("/subir", { method: "POST", body: datos });
        const resultado = await respuesta.json();
        if (!respuesta.ok) throw new Error(resultado.error);
        editor.value = resultado.codigo;
        mensaje.textContent = "Archivo cargado.";
    } catch (error) {
        mensaje.textContent = error.message || "No se pudo cargar el archivo.";
    }
});

botonAnalizar.addEventListener("click", async () => {
    if (!editor.value.trim()) {
        mensaje.textContent = "Escribe una regla primero.";
        return;
    }

    botonAnalizar.disabled = true;
    mensaje.textContent = "Analizando...";

    try {
        const respuesta = await fetch("/analizar", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ codigo: editor.value })
        });
        const resultado = await respuesta.json();
        if (!respuesta.ok) throw new Error(resultado.error || "Error de análisis.");

        mostrarTokens(resultado.tokens || []);
        mostrarER(resultado.expresiones || []);
        mostrarReglas(resultado.reglas || []);
        mostrarAutomatas(resultado.automatas || []);
        mostrarErrores(resultado.errores || []);

        document.getElementById("totalTokens").textContent = resultado.tokens.length;
        document.getElementById("totalErrores").textContent = resultado.errores.length;
        document.getElementById("estadoResultado").textContent =
            resultado.valido ? "Sin errores" : "Revisar reglas";
        mensaje.textContent = "Análisis completado.";
    } catch (error) {
        mensaje.textContent = "Error: " + error.message;
    } finally {
        botonAnalizar.disabled = false;
    }
});

function nodo(tag, texto, clase) {
    const el = document.createElement(tag);
    if (texto !== undefined) el.textContent = String(texto);
    if (clase) el.className = clase;
    return el;
}

function filaVacia(tbody, columnas, texto) {
    const fila = document.createElement("tr");
    const celda = nodo("td", texto);
    celda.colSpan = columnas;
    fila.appendChild(celda);
    tbody.appendChild(fila);
}

function agregarFila(tbody, valores) {
    const fila = document.createElement("tr");
    valores.forEach(v => fila.appendChild(nodo("td", v ?? "—")));
    tbody.appendChild(fila);
}

function mostrarTokens(tokens) {
    const tbody = document.getElementById("tablaTokens");
    tbody.replaceChildren();
    if (!tokens.length) return filaVacia(tbody, 3, "No se identificaron tokens.");
    tokens.forEach(t => agregarFila(tbody, [t.token, t.lexema, t.posicion]));
}

function mostrarER(expresiones) {
    const tbody = document.getElementById("tablaER");
    tbody.replaceChildren();
    if (!expresiones.length) return filaVacia(tbody, 2, "Sin ER.");
    expresiones.forEach(e => agregarFila(tbody, [e.tipo, e.expresion]));
}

function mostrarReglas(reglas) {
    const tbody = document.getElementById("tablaReglas");
    tbody.replaceChildren();
    if (!reglas.length) return filaVacia(tbody, 3, "No hay reglas.");
    reglas.forEach(r => agregarFila(tbody, [
        r.linea, r.regla, r.coincide ? "Válida" : "Inválida"
    ]));
}

function bloqueCodigo(texto) {
    return nodo("pre", texto, "codigo-salida");
}

function tablaTransiciones(transiciones) {
    const envoltura = nodo("div", undefined, "tabla-contenedor");
    const tabla = document.createElement("table");
    const thead = document.createElement("thead");
    const fila = document.createElement("tr");

    ["Origen", "Símbolo", "Destino"].forEach(t => fila.appendChild(nodo("th", t)));
    thead.appendChild(fila);
    tabla.appendChild(thead);

    const tbody = document.createElement("tbody");
    if (!transiciones || !transiciones.length) {
        filaVacia(tbody, 3, "Sin transiciones.");
    } else {
        transiciones.forEach(t => agregarFila(tbody, [t.origen, t.simbolo, t.destino]));
    }

    tabla.appendChild(tbody);
    envoltura.appendChild(tabla);
    return envoltura;
}

function tablaMatrizAFD(afd) {
    const envoltura = nodo("div", undefined, "tabla-contenedor");
    const tabla = document.createElement("table");
    const thead = document.createElement("thead");
    const cabecera = document.createElement("tr");

    cabecera.appendChild(nodo("th", "Estado"));
    (afd.alfabeto || []).forEach(s => cabecera.appendChild(nodo("th", s)));
    cabecera.appendChild(nodo("th", "Tipo"));
    thead.appendChild(cabecera);
    tabla.appendChild(thead);

    const tbody = document.createElement("tbody");

    (afd.estados || []).forEach(estado => {
        const fila = document.createElement("tr");
        fila.appendChild(nodo("td", estado));

        (afd.alfabeto || []).forEach(simbolo => {
            const t = (afd.transiciones || []).find(
                x => x.origen === estado && x.simbolo === simbolo
            );
            fila.appendChild(nodo("td", t ? t.destino : "—"));
        });

        const tipo = [];
        if (estado === afd.inicial) tipo.push("Inicial");
        if ((afd.finales || []).includes(estado)) tipo.push("Final");
        if (!tipo.length) tipo.push("Intermedio");
        fila.appendChild(nodo("td", tipo.join(" / ")));
        tbody.appendChild(fila);
    });

    tabla.appendChild(tbody);
    envoltura.appendChild(tabla);
    return envoltura;
}

function mostrarAutomatas(automatas) {
    const contenedor = document.getElementById("contenedorAutomatas");
    contenedor.replaceChildren();

    if (!automatas.length) {
        contenedor.textContent = "No se generaron autómatas.";
        return;
    }

    automatas.forEach((item, i) => {
        const seccion = nodo("section", undefined, "automata-card");
        seccion.appendChild(nodo("h3", `${i + 1}. ${item.tipo}`));

        seccion.appendChild(nodo("h4", "Expresión regular"));
        seccion.appendChild(bloqueCodigo(item.expresion_regular));

        seccion.appendChild(nodo("h4", "AFND: quíntupla"));
        seccion.appendChild(bloqueCodigo(JSON.stringify(item.quintupla_afnd, null, 2)));
        seccion.appendChild(nodo("h4", "Transiciones del AFND"));
        seccion.appendChild(tablaTransiciones(item.afnd.transiciones));

        seccion.appendChild(nodo("h4", "AFD: quíntupla"));
        seccion.appendChild(bloqueCodigo(JSON.stringify(item.quintupla_afd, null, 2)));

        seccion.appendChild(nodo("h4", "Tabla completa de transiciones del AFD"));
        seccion.appendChild(tablaMatrizAFD(item.afd));

        seccion.appendChild(nodo("h4", "Gráfico del AFD"));
        const grafico = nodo("div", undefined, "grafico-contenedor");
        dibujarAFD(item.afd, grafico);
        seccion.appendChild(grafico);

        contenedor.appendChild(seccion);
    });
}

function mostrarErrores(errores) {
    const contenedor = document.getElementById("listaErrores");
    contenedor.replaceChildren();

    if (!errores.length) {
        contenedor.appendChild(nodo("div", "No se detectaron errores.", "exito"));
        return;
    }

    errores.forEach(e => {
        contenedor.appendChild(nodo(
            "div", `Línea ${e.posicion}: ${e.mensaje}`, "error"
        ));
    });
}

function dibujarAFD(afd, contenedor) {
    contenedor.replaceChildren();

    const estados = afd.estados || [];
    const transiciones = afd.transiciones || [];
    if (!estados.length) {
        contenedor.textContent = "No hay estados.";
        return;
    }

    const ns = "http://www.w3.org/2000/svg";
    const ancho = Math.max(650, estados.length * 125);
    const alto = 240;
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", `0 0 ${ancho} ${alto}`);
    svg.setAttribute("width", "100%");
    svg.setAttribute("role", "img");

    const defs = document.createElementNS(ns, "defs");
    const marker = document.createElementNS(ns, "marker");
    marker.setAttribute("id", "flecha-rulecheck");
    marker.setAttribute("markerWidth", "8");
    marker.setAttribute("markerHeight", "8");
    marker.setAttribute("refX", "7");
    marker.setAttribute("refY", "3");
    marker.setAttribute("orient", "auto");
    const punta = document.createElementNS(ns, "path");
    punta.setAttribute("d", "M0,0 L0,6 L8,3 z");
    punta.setAttribute("fill", "#315fe8");
    marker.appendChild(punta);
    defs.appendChild(marker);
    svg.appendChild(defs);

    const posiciones = {};
    estados.forEach((e, i) => {
        posiciones[e] = {
            x: 55 + i * ((ancho - 110) / Math.max(1, estados.length - 1)),
            y: 120
        };
    });

    const grupos = new Map();
    transiciones.forEach(t => {
        const clave = `${t.origen}::${t.destino}`;
        if (!grupos.has(clave)) grupos.set(clave, []);
        grupos.get(clave).push(t.simbolo);
    });

    grupos.forEach((simbolos, clave) => {
        const [origen, destino] = clave.split("::");
        const a = posiciones[origen], b = posiciones[destino];
        if (!a || !b) return;

        if (origen === destino) {
            const arco = document.createElementNS(ns, "path");
            arco.setAttribute("d", `M ${a.x-12} ${a.y-20} C ${a.x-48} ${a.y-80}, ${a.x+48} ${a.y-80}, ${a.x+12} ${a.y-20}`);
            arco.setAttribute("fill", "none");
            arco.setAttribute("stroke", "#315fe8");
            arco.setAttribute("marker-end", "url(#flecha-rulecheck)");
            svg.appendChild(arco);
            const texto = nodo("title", simbolos.join(", "));
            arco.appendChild(texto);
            return;
        }

        const dx = b.x - a.x, dy = b.y - a.y;
        const d = Math.hypot(dx, dy) || 1;
        const linea = document.createElementNS(ns, "line");
        linea.setAttribute("x1", a.x + dx/d*24);
        linea.setAttribute("y1", a.y + dy/d*24);
        linea.setAttribute("x2", b.x - dx/d*29);
        linea.setAttribute("y2", b.y - dy/d*29);
        linea.setAttribute("stroke", "#315fe8");
        linea.setAttribute("marker-end", "url(#flecha-rulecheck)");
        svg.appendChild(linea);

        const etiqueta = document.createElementNS(ns, "text");
        etiqueta.setAttribute("x", (a.x+b.x)/2);
        etiqueta.setAttribute("y", (a.y+b.y)/2-8);
        etiqueta.setAttribute("text-anchor", "middle");
        etiqueta.setAttribute("font-size", "10");
        etiqueta.textContent = simbolos.join(", ");
        svg.appendChild(etiqueta);
    });

    estados.forEach(e => {
        const p = posiciones[e];
        const circulo = document.createElementNS(ns, "circle");
        circulo.setAttribute("cx", p.x);
        circulo.setAttribute("cy", p.y);
        circulo.setAttribute("r", 24);
        circulo.setAttribute("fill", "#e8efff");
        circulo.setAttribute("stroke", "#315fe8");
        circulo.setAttribute("stroke-width", "2");
        svg.appendChild(circulo);

        if ((afd.finales || []).includes(e)) {
            const interior = document.createElementNS(ns, "circle");
            interior.setAttribute("cx", p.x);
            interior.setAttribute("cy", p.y);
            interior.setAttribute("r", 19);
            interior.setAttribute("fill", "none");
            interior.setAttribute("stroke", "#315fe8");
            svg.appendChild(interior);
        }

        const texto = document.createElementNS(ns, "text");
        texto.setAttribute("x", p.x);
        texto.setAttribute("y", p.y+4);
        texto.setAttribute("text-anchor", "middle");
        texto.setAttribute("font-size", "11");
        texto.textContent = e;
        svg.appendChild(texto);
    });

    contenedor.appendChild(svg);
}

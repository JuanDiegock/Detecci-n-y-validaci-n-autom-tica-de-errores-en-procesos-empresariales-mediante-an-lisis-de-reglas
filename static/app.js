const $ = (id) => document.getElementById(id);
const campos = ["Nombre","Apellido","DNI","Edad","Diagnostico","Fecha","Hora","Hospital/Clinica","Laboratorio","Salon","Examenes","Enfermera/Medico","Tipo de sangre"];
const ejemplo = `Nombre: Juan
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
Tipo de sangre: A+`;
const ejemploDSL = `REGISTRO_MEDICO {
NOMBRE: Juan
APELLIDO: Perez
DNI: 12345678
EDAD: 30
DIAGNOSTICO: J00
FECHA: 2025-06-10
HORA: 09:15
HOSPITAL_CLINICA: Clinica Central
LABORATORIO: Lab Uno
SALON: MI-P2-103
EXAMENES: Hemograma
ENFERMERA_MEDICO: Dra Lopez
TIPO_SANGRE: A+
}`;
$("ejemploCodigoDsl").textContent = ejemploDSL;

document.querySelectorAll('input[name="modo"]').forEach(r => r.addEventListener("change", () => {
  ["Formulario","Archivo","Dsl"].forEach((name, i) => $("modo"+name).classList.toggle("oculto", ["formulario","archivo","dsl"][i] !== r.value));
  $("mensaje").textContent = "Modalidad seleccionada: " + r.parentElement.textContent.trim();
}));

$("ejemploFormulario").addEventListener("click", () => {
  const values = Object.fromEntries(ejemplo.split("\n").map(l => { const i=l.indexOf(":"); return [l.slice(0,i),l.slice(i+1).trim()]; }));
  const form = $("formRegistro");
  Object.entries(values).forEach(([k,v]) => { if(form.elements[k]) form.elements[k].value=v; });
  $("mensaje").textContent = "Ejemplo cargado en la plantilla.";
});
$("ejemploDsl").addEventListener("click", () => { $("codigoDsl").value=ejemploDSL; $("mensaje").textContent="Ejemplo DSL cargado."; });
$("descargarPlantilla").addEventListener("click", () => descargarTxt("plantilla_rulecheck.txt", ejemplo.split("\n").map(l=>l.replace(/:.*/,": ")).join("\n")));
function descargarTxt(nombre, contenido) {
  const blob = new Blob([contenido], {type:"text/plain;charset=utf-8"});
  const url = URL.createObjectURL(blob); const a=document.createElement("a");
  a.href=url; a.download=nombre; a.click(); URL.revokeObjectURL(url);
}
$("formRegistro").addEventListener("submit", e => {
  e.preventDefault();
  const fd = new FormData(e.currentTarget);
  const lineas = campos.map(c => `${c}: ${String(fd.get(c)||"").trim()}`);
  analizar(lineas.join("\n"));
});
$("analizarDsl").addEventListener("click", () => analizar($("codigoDsl").value));
$("analizarArchivo").addEventListener("click", async () => {
  const f=$("archivo").files[0];
  if(!f) return $("mensaje").textContent="Selecciona primero un archivo .txt.";
  if(!f.name.toLowerCase().endsWith(".txt")) return $("mensaje").textContent="Solo se permiten archivos .txt.";
  const fd=new FormData(); fd.append("archivo",f);
  try {
    const res=await fetch("/subir",{method:"POST",body:fd}); const data=await res.json();
    if(!res.ok) throw new Error(data.error||"No se pudo cargar el archivo.");
    await analizar(data.codigo);
  } catch(err) { $("mensaje").textContent="Error: "+err.message; }
});
$("archivo").addEventListener("change", () => { if($("archivo").files[0]) $("mensaje").textContent="Archivo seleccionado. Presiona «Analizar y validar registro»."; });

async function analizar(codigo) {
  if(!codigo.trim()) return $("mensaje").textContent="Ingresa o carga un registro antes de analizar.";
  $("mensaje").textContent="Analizando el registro...";
  document.querySelectorAll(".principal").forEach(b=>b.disabled=true);
  try {
    const res=await fetch("/analizar",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({codigo})});
    const data=await res.json(); if(!res.ok) throw new Error(data.error||"No se pudo analizar.");
    mostrarTokens(data.tokens||[]); mostrarER(data.expresiones||[]); mostrarReglas(data.reglas||[]);
    mostrarAutomatas(data.automatas||[]); mostrarErrores(data.errores||[]);
    $("totalTokens").textContent=(data.tokens||[]).length;
    $("totalErrores").textContent=(data.errores||[]).length;
    const validos=(data.reglas||[]).filter(r=>r.coincide).length;
    $("totalValidos").textContent=`${Math.min(validos,13)} / 13`;
    $("estadoResultado").textContent=data.valido?"Registro válido":"Requiere correcciones";
    $("estadoResultado").className="insignia "+(data.valido?"ok":"alerta");
    $("mensaje").textContent=data.valido?"Análisis completado. Los 13 campos cumplen los formatos establecidos.":"Análisis completado. Revisa los errores y las observaciones del reporte.";
    $("resultados").scrollIntoView({behavior:"smooth",block:"start"});
  } catch(err) { $("mensaje").textContent="Error: "+err.message; }
  finally { document.querySelectorAll(".principal").forEach(b=>b.disabled=false); }
}
function node(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=String(text);if(cls)e.className=cls;return e;}
function emptyRow(tbody,n,msg){const tr=document.createElement("tr"),td=node("td",msg);td.colSpan=n;tr.appendChild(td);tbody.appendChild(tr);}
function addRow(tbody,values){const tr=document.createElement("tr");values.forEach(v=>tr.appendChild(node("td",v??"—")));tbody.appendChild(tr);}
function renderTable(id,rows,n,empty){
  const tb=$(id);tb.replaceChildren();if(!rows.length){emptyRow(tb,n,empty);return;}
  rows.forEach(r=>addRow(tb,r));
}
function mostrarTokens(tokens){renderTable("tablaTokens",tokens.map(t=>[t.token,t.lexema,t.posicion,t.descripcion||"—",t.ejemplo||"—"]),5,"No se identificaron tokens.");}
function mostrarER(items){renderTable("tablaER",items.map(e=>[e.tipo,e.descripcion||"Patrón de reconocimiento",e.ejemplo||"—",e.expresion]),4,"Sin expresiones regulares.");}
function mostrarReglas(items){renderTable("tablaReglas",items.map(r=>[r.linea,r.regla,r.coincide?"Válido":"Inválido",r.detalle||""]),4,"No hay campos para validar.");}
function mostrarErrores(items){
  const box=$("listaErrores");box.replaceChildren();
  if(!items.length){box.appendChild(node("div","No se detectaron errores. Los 13 campos cumplen las reglas definidas.","exito"));return;}
  items.forEach(e=>box.appendChild(node("div",`Línea ${e.posicion}: ${e.mensaje}`,"error")));
}
function tableTransitions(transitions){
  const wrap=node("div",undefined,"tabla-contenedor tabla-transiciones");
  const table=document.createElement("table"),thead=document.createElement("thead"),tr=document.createElement("tr");
  ["Origen","Símbolo","Destino"].forEach(x=>tr.appendChild(node("th",x)));
  thead.appendChild(tr);table.appendChild(thead);
  const tb=document.createElement("tbody");
  if(!transitions?.length)emptyRow(tb,3,"Sin transiciones.");
  else transitions.forEach(t=>addRow(tb,[t.origen,t.simbolo,t.destino]));
  table.appendChild(tb);wrap.appendChild(table);return wrap;
}
function quintupla(a){
  const wrap=node("div",undefined,"tabla-contenedor");
  const p=node("p","M = (Q, Σ, δ, q₀, F)","formula-quintupla");wrap.appendChild(p);
  const table=document.createElement("table"),thead=document.createElement("thead"),tr=document.createElement("tr");
  ["Componente","Valor"].forEach(x=>tr.appendChild(node("th",x)));thead.appendChild(tr);table.appendChild(thead);
  const tb=document.createElement("tbody");
  [[ "Q - Estados",`{ ${a.estados.join(", ")} }`],["Σ - Alfabeto",`{ ${a.alfabeto.join(", ")} }`],["δ - Transiciones","Ver tabla de transiciones"],["q₀ - Estado inicial",a.inicial],["F - Estados finales",`{ ${a.finales.join(", ")} }`]].forEach(r=>addRow(tb,r));
  table.appendChild(tb);wrap.appendChild(table);return wrap;
}
let diagramCount=0;
function compactSymbol(symbol){
  if (/^\d$/.test(symbol)) return "D";
  if (/^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]$/.test(symbol)) return "L";
  return symbol;
}
function makeDiagram(a,type){
  const ns="http://www.w3.org/2000/svg", svg=document.createElementNS(ns,"svg");
  const states=a.estados||[], raw=a.transiciones||[], finals=new Set(a.finales||[]);
  const perRow=5, gapX=145, gapY=155, marginX=78, marginY=82, radius=25;
  const rows=Math.max(1,Math.ceil(states.length/perRow));
  const width=Math.max(760,marginX*2+(perRow-1)*gapX+80), height=Math.max(310,marginY*2+(rows-1)*gapY+70);
  svg.setAttribute("viewBox",`0 0 ${width} ${height}`);svg.setAttribute("role","img");svg.setAttribute("aria-label",`${type} de ${a.tipo}`);
  const defs=document.createElementNS(ns,"defs"),marker=document.createElementNS(ns,"marker"),id=`arr-${++diagramCount}`;
  marker.setAttribute("id",id);marker.setAttribute("markerWidth","9");marker.setAttribute("markerHeight","9");marker.setAttribute("refX","8");marker.setAttribute("refY","3");marker.setAttribute("orient","auto");
  const tip=nodeSvg("path","");tip.setAttribute("d","M0,0 L0,6 L8,3 z");tip.setAttribute("fill",type==="AFND"?"#2679b8":"#218653");marker.appendChild(tip);defs.appendChild(marker);svg.appendChild(defs);
  const pos={};
  states.forEach((state,i)=>{const row=Math.floor(i/perRow),idx=i%perRow,col=row%2===0?idx:perRow-1-idx;pos[state]={x:marginX+col*gapX,y:marginY+row*gapY};});
  const color=type==="AFND"?"#2679b8":"#218653";
  // Agrupa transiciones paralelas para evitar etiquetas y flechas superpuestas.
  const grouped=new Map();
  raw.forEach(t=>{const key=`${t.origen}→${t.destino}`;if(!grouped.has(key))grouped.set(key,{origen:t.origen,destino:t.destino,simbolos:[]});grouped.get(key).simbolos.push(t.simbolo);});
  const edges=[...grouped.values()];
  edges.forEach((t,i)=>{
    const a1=pos[t.origen],b=pos[t.destino];if(!a1||!b)return;
    const path=document.createElementNS(ns,"path");let d,lx,ly;
    if(t.origen===t.destino){d=`M${a1.x-13},${a1.y-radius+2} C${a1.x-48},${a1.y-83} ${a1.x+48},${a1.y-83} ${a1.x+13},${a1.y-radius+2}`;lx=a1.x;ly=a1.y-61;}
    else {
      const dx=b.x-a1.x,dy=b.y-a1.y;
      const offset=((i%3)-1)*15;
      const mx=(a1.x+b.x)/2-dy/(Math.hypot(dx,dy)||1)*offset;
      const my=(a1.y+b.y)/2+dx/(Math.hypot(dx,dy)||1)*offset-((Math.abs(dy)<5)?28:0);
      d=`M${a1.x+Math.sign(dx||1)*radius},${a1.y} Q${mx},${my} ${b.x-Math.sign(dx||1)*radius},${b.y}`;lx=mx;ly=my-8;
    }
    path.setAttribute("d",d);path.setAttribute("fill","none");path.setAttribute("stroke",color);path.setAttribute("stroke-width","2");path.setAttribute("marker-end",`url(#${id})`);svg.appendChild(path);
    const labels=[...new Set(t.simbolos.map(compactSymbol))];
    const label=nodeSvg("text",labels.length>4?`${labels.slice(0,3).join(", ")}…`:labels.join(", "));
    label.setAttribute("x",lx);label.setAttribute("y",ly);label.setAttribute("text-anchor","middle");label.setAttribute("class","etiqueta-transicion");svg.appendChild(label);
  });
  states.forEach(state=>{
    const p=pos[state],g=document.createElementNS(ns,"g"),circle=document.createElementNS(ns,"circle"),txt=nodeSvg("text",state);
    circle.setAttribute("cx",p.x);circle.setAttribute("cy",p.y);circle.setAttribute("r",radius);
    circle.setAttribute("fill",state===a.inicial?"#dff3e7":(finals.has(state)?"#e1f5e8":"#eaf2fb"));circle.setAttribute("stroke",finals.has(state)?"#218653":color);circle.setAttribute("stroke-width","2.7");
    if(finals.has(state)){const inner=document.createElementNS(ns,"circle");inner.setAttribute("cx",p.x);inner.setAttribute("cy",p.y);inner.setAttribute("r",radius-5);inner.setAttribute("fill","none");inner.setAttribute("stroke","#218653");inner.setAttribute("stroke-width","1.8");g.appendChild(inner);}
    txt.setAttribute("x",p.x);txt.setAttribute("y",p.y+5);txt.setAttribute("text-anchor","middle");txt.setAttribute("class","nombre-estado");
    g.appendChild(circle);g.appendChild(txt);svg.appendChild(g);
  });
  const sp=pos[a.inicial];if(sp){const start=document.createElementNS(ns,"path");start.setAttribute("d",`M${sp.x-62},${sp.y} L${sp.x-29},${sp.y}`);start.setAttribute("stroke","#344054");start.setAttribute("stroke-width","2");start.setAttribute("marker-end",`url(#${id})`);svg.appendChild(start);}
  return svg;
}
function nodeSvg(tag,text){const e=document.createElementNS("http://www.w3.org/2000/svg",tag);e.textContent=text;return e;}
function diagramPanel(a,type){
  const card=node("section",undefined,`panel-diagrama ${type.toLowerCase()}`);
  card.appendChild(node("h4",`${type} — ${type==="AFND"?"Autómata Finito No Determinista":"Autómata Finito Determinista"}`));
  card.appendChild(node("p",`Expresión regular: ${a.expresion_regular||""}`));
  const frame=node("div",undefined,"marco-diagrama");frame.appendChild(makeDiagram(a,type));card.appendChild(frame);
  const legend=node("div",undefined,"leyenda");legend.textContent="● Estado inicial     ○ Estado intermedio     ◎ Estado de aceptación     → Transición etiquetada. D = dígito; L = letra; ε = cadena vacía.";card.appendChild(legend);
  card.appendChild(node("p",`Estados: ${a.estados.length} · Estado inicial: ${a.inicial} · Estados finales: ${(a.finales||[]).join(", ")}`,"resumen-automata"));
  return card;
}
function mostrarAutomatas(items){
  const box=$("contenedorAutomatas");box.replaceChildren();
  if(!items.length){box.textContent="No se generaron autómatas.";return;}
  items.forEach((item,i)=>{
    const card=node("section",undefined,"automata-card");
    card.appendChild(node("h3",`${i+1}. Autómata para ${item.tipo}`));
    card.appendChild(node("p",`Expresión regular: ${item.expresion_regular}`));
    const duo=node("div",undefined,"quintuplas-grid");
    const q1=node("section",undefined,"subpanel");q1.appendChild(node("h4","Quíntupla del AFND"));q1.appendChild(quintupla(item.afnd));q1.appendChild(node("h4","Transiciones del AFND"));q1.appendChild(tableTransitions(item.afnd.transiciones));
    const q2=node("section",undefined,"subpanel");q2.appendChild(node("h4","Quíntupla del AFD"));q2.appendChild(quintupla(item.afd));q2.appendChild(node("h4","Transiciones del AFD"));q2.appendChild(tableTransitions(item.afd.transiciones));
    duo.append(q1,q2);card.appendChild(duo);
    const graphs=node("div",undefined,"comparacion-automatas");
    graphs.appendChild(diagramPanel({...item.afnd,expresion_regular:item.expresion_regular},"AFND"));
    graphs.appendChild(diagramPanel({...item.afd,expresion_regular:item.expresion_regular},"AFD"));
    card.appendChild(node("h4","Diagramas de los autómatas"));card.appendChild(graphs);box.appendChild(card);
  });
}

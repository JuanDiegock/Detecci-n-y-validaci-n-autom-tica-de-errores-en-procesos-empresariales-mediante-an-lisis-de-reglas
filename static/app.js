const $=id=>document.getElementById(id);
const CAMPOS=["NOMBRE","APELLIDO","DNI","EDAD","DIAGNOSTICO","FECHA","HORA","TIPO_SANGRE","EXAMENES","HOSPITAL_CLINICA","LABORATORIO","SALON","ENFERMERA_MEDICO"];
const GRUPOS=[
 {token:"mis_variables_numericas",campos:["DNI","EDAD"],funcion:"Valores numéricos",color:"violet"},
 {token:"mis_variables_texto",campos:["NOMBRE","APELLIDO","DIAGNOSTICO","EXAMENES","HOSPITAL_CLINICA","LABORATORIO","SALON","ENFERMERA_MEDICO"],funcion:"Valores de texto",color:"blue"},
 {token:"mis_variables_fecha",campos:["FECHA"],funcion:"Fecha calendario",color:"green"},
 {token:"mis_variables_hora",campos:["HORA"],funcion:"Hora HH:MM",color:"orange"},
 {token:"mis_variables_sanguineas",campos:["TIPO_SANGRE"],funcion:"Grupo sanguíneo",color:"pink"},
 {token:"separadores",campos:[":"],funcion:"Separador campo / valor",color:"slate"}
];
const EJEMPLO=`REGISTRO_MEDICO {
NOMBRE: Juan
APELLIDO: Perez
DNI: 12345678
EDAD: 30
DIAGNOSTICO: J00
FECHA: 2025-06-10
HORA: 09:15
TIPO_SANGRE: A+
EXAMENES: Hemograma
HOSPITAL_CLINICA: Clinica Central
LABORATORIO: Lab Uno
SALON: MI-P2-103
ENFERMERA_MEDICO: Dra Lopez
}`;
const DESCRIPCIONES={
NOMBRE:"Nombre del trabajador",APELLIDO:"Apellido del trabajador",DNI:"Documento de identidad de ocho dígitos",EDAD:"Edad entre 1 y 120 años",DIAGNOSTICO:"Código o descripción del diagnóstico",FECHA:"Fecha válida AAAA-MM-DD",HORA:"Hora válida HH:MM",TIPO_SANGRE:"Grupo sanguíneo y factor RH",EXAMENES:"Exámenes médicos realizados",HOSPITAL_CLINICA:"Centro de atención",LABORATORIO:"Laboratorio responsable",SALON:"Código de salón o consultorio",ENFERMERA_MEDICO:"Profesional responsable"
};
let ultimo=null, automatas=[], campoSeleccionado="DNI";
function mode(){return document.querySelector('input[name="modo"]:checked').value;}
function changeMode(){const m=mode();["plantilla","archivo","dsl"].forEach(x=>$(x).classList.toggle("hidden",x!==m));document.querySelectorAll(".mode-option").forEach(x=>x.classList.toggle("selected",x.querySelector("input").checked));}
document.querySelectorAll('input[name="modo"]').forEach(x=>x.addEventListener("change",changeMode));
function plantillaDSL(){return "REGISTRO_MEDICO {\n"+CAMPOS.map(c=>`${c}: ${($(c).value||"").trim()}`).join("\n")+"\n}";}
async function textoEntrada(){if(mode()==="plantilla")return plantillaDSL();if(mode()==="dsl")return $("codigoDSL").value.trim();const f=$("archivoTxt").files[0];if(!f)throw Error("Selecciona un archivo TXT.");if(!f.name.toLowerCase().endsWith(".txt"))throw Error("El archivo debe tener extensión .txt.");return await f.text();}
function notice(msg,kind="success"){const el=$("mensaje");el.textContent=msg;el.className=`notice ${kind}`;}
function esc(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function cellRow(values){const tr=document.createElement("tr");values.forEach(v=>{const td=document.createElement("td");td.textContent=String(v??"");tr.appendChild(td);});return tr;}
function fill(id,rows){const b=$(id);b.innerHTML="";rows.forEach(r=>b.appendChild(cellRow(r)));}
function valueToken(campo){const mapping={DNI:"VALOR_NUMERICO",EDAD:"VALOR_NUMERICO",FECHA:"VALOR_FECHA",HORA:"VALOR_HORA",TIPO_SANGRE:"VALOR_SANGUINEO"};return mapping[campo]||"VALOR_TEXTO";}
function tokenAgrupador(campo){return GRUPOS.find(g=>g.campos.includes(campo))?.token||"—";}
function regexLiteralAlternation(values){
 return "^("+values.map(v=>v.replace(/[.*+?^${}()|[\\]\\\\]/g,"\\\\$&")).join("|")+")$";
}
function setNotation(values){
 if(values[0]===":") return 'L = { x ∈ Σ* | x = ":" }';
 return "L = { "+values.map(v=>'"'+v+'"').join(", ")+" }";
}
function setBuilderNotation(values){
 if(values[0]===":") return '{ x ∈ Σ* | x = ":" }';
 return "{ x ∈ Σ* | "+values.map(v=>'x = "'+v+'"').join(" ∨ ")+" }";
}
function renderGroups(r){
 const rows=GRUPOS.map(g=>{
  const values=g.campos;
  const regex=regexLiteralAlternation(values);
  const language=setNotation(values);
  const sets=setBuilderNotation(values);
  return [g.token,values.join(", "),regex,language,sets];
 });
 fill("tablaGrupos",rows);
 const relation=[];
 CAMPOS.forEach(c=>{const g=GRUPOS.find(x=>x.campos.includes(c));relation.push([g.token,c,r.expresiones.find(x=>x.lexema===c)?.regex||"—",`AFND / AFD de ${c}`]);});
 relation.push(["separadores",":","Símbolo literal ':'","Transición de separación"]);
 fill("tablaRelacion",relation);
 fill("tablaER",(r.expresiones||[]).map(e=>[e.lexema,e.regex,(data[e.lexema]??exampleValue(e.lexema)),DESCRIPCIONES[e.lexema]||"Regla de campo"]));
}
function exampleValue(c){return ({NOMBRE:"Juan",APELLIDO:"Perez",DNI:"12345678",EDAD:"30",DIAGNOSTICO:"J00",FECHA:"2025-06-10",HORA:"09:15",TIPO_SANGRE:"A+",EXAMENES:"Hemograma",HOSPITAL_CLINICA:"Clinica Central",LABORATORIO:"Lab Uno",SALON:"MI-P2-103",ENFERMERA_MEDICO:"Dra Lopez"})[c]||"";}
function renderSequence(r){
 const syn=r.tokens_sintacticos||[], rows=[];
 syn.forEach(t=>{
  let token=t.tipo, lex=t.lexema;
  if(t.tipo==="REGISTRO_MEDICO")token="TK_DECLARACION";
  else if(t.tipo==="LLAVE_ABRE"||t.tipo==="LLAVE_CIERRA")token="TK_LLAVE";
  else if(t.tipo==="IDENTIFICADOR")token=tokenAgrupador(t.lexema);
  else if(t.tipo==="DOS_PUNTOS")token="separadores";
  else if(t.tipo.startsWith("VALOR_"))token=t.tipo;
  rows.push([rows.length+1,token,lex,t.linea]);
 });
 fill("tablaSecuencia",rows);
 $("secuenciaSintactica").textContent=syn.map(t=>`${t.tipo}  →  ${t.lexema}  (línea ${t.linea})`).join("\n")||"No se reconocieron terminales.";
}
function renderGrammar(r){
 const formal=$("gramaticaFormal");
 formal.textContent="G = (V, T, P, S)\\nV = {S, REGISTRO, LISTA_CAMPOS, CAMPO, IDENTIFICADOR, VALOR}\\nT = {REGISTRO_MEDICO, LLAVE_ABRE, LLAVE_CIERRA, DOS_PUNTOS, VALOR_TEXTO, VALOR_NUMERICO, VALOR_FECHA, VALOR_HORA, VALOR_SANGUINEO}\\nP = producciones mostradas en la tabla siguiente\\nS = REGISTRO";
 fill("tablaGramatica",(r.producciones||[]).map((p,i)=>[i+1,p]));
 fill("tablaPasos",(r.pasos_sintacticos||[]).map((p,i)=>[i+1,p]));
 const errors=r.errores_sintacticos||[];
 $("estadoSintactico").textContent=errors.length?("Cadena rechazada por el parser:\n"+errors.join("\n")):"La estructura fue aceptada por el parser descendente. Se aplicaron las producciones de la gramática.";
 $("estadoSintactico").className="status-box "+(errors.length?"bad":"good");
}
function renderTree(node,depth=0){
 const wrap=document.createElement("div");wrap.className="tree-node";
 const label=document.createElement("span");label.textContent=node.nombre;wrap.appendChild(label);
 if(node.hijos?.length){const children=document.createElement("div");children.className="tree-children";node.hijos.forEach(ch=>children.appendChild(renderTree(ch,depth+1)));wrap.appendChild(children);}
 return wrap;
}
function treeInto(id,node){const el=$(id);el.innerHTML="";if(node)el.appendChild(renderTree(node));}
function renderSemantic(r){
 const data=r.datos||{}, errors=r.errores||[];
 const rows=CAMPOS.map(c=>{const val=data[c]??"—", exists=Object.hasOwn(data,c), invalid=errors.some(e=>e.startsWith(c+":"));return [c,valueToken(c),val,DESCRIPCIONES[c],!exists?"FALTANTE":invalid?"INVÁLIDO":"VÁLIDO"];});
 fill("tablaSemantica",rows);
 $("atributosSintetizados").textContent=`campos_reconocidos = ${r.campos_reconocidos}/${r.total_campos}\ntokens_reconocidos = ${r.total_tokens}\nregistro_valido = ${r.valido}\nestado = ${r.estado}`;
 $("atributosHeredados").textContent="contexto = REGISTRO_MEDICO\ntipos_esperados = configuración de CAMPOS\nreglas = campos obligatorios + expresiones regulares + restricciones de dominio";
 const sem={nombre:"REGISTRO_MEDICO",hijos:CAMPOS.map(c=>({nombre:`${c} · ${Object.hasOwn(data,c)?"PRESENTE":"FALTANTE"}`,hijos:[{nombre:String(data[c]??"—"),hijos:[]}]}))};
 treeInto("arbolSemantico",sem);
}
function svg(tag,attrs={}){const e=document.createElementNS("http://www.w3.org/2000/svg",tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));return e;}
function groupTransitions(transitions){const map=new Map();transitions.forEach(t=>{const key=t.from+"|"+t.to;map.set(key,[...(map.get(key)||[]),t.symbol]);});return [...map.entries()].map(([key,symbols])=>{const [from,to]=key.split("|");return {from,to,symbols};});}
function graphFor(automaton,type){
 const states=automaton.states||[];
 const transitions=type==="AFND"
  ?states.flatMap(s=>(s.transitions||[]).map(t=>({from:s.id,to:t.to,symbol:t.symbol})))
  :(automaton.transitions||[]).map(t=>({from:t.from,to:t.to,symbol:t.symbol}));
 const byId=new Map(states.map(s=>[s.id,s]));
 const outgoing=new Map(states.map(s=>[s.id,[]]));
 transitions.forEach(t=>{if(outgoing.has(t.from))outgoing.get(t.from).push(t);});
 // JFLAP-like layered layout: initial state at left, accepting states toward the right.
 const start=automaton.start||states[0]?.id;
 const level=new Map(); if(start)level.set(start,0);
 const queue=start?[start]:[];
 while(queue.length){
  const current=queue.shift();
  for(const edge of outgoing.get(current)||[]){
   if(!level.has(edge.to)){level.set(edge.to,level.get(current)+1);queue.push(edge.to);}
  }
 }
 // Keep unreachable states visible in subsequent columns.
 let maxLevel=Math.max(0,...level.values());
 states.forEach(s=>{if(!level.has(s.id)){maxLevel++;level.set(s.id,maxLevel);}});
 const buckets=new Map();
 states.forEach(s=>{const l=level.get(s.id);if(!buckets.has(l))buckets.set(l,[]);buckets.get(l).push(s);});
 const xGap=116,yGap=86,left=68,top=66,radius=19;
 const maxRows=Math.max(1,...[...buckets.values()].map(a=>a.length));
 const width=Math.max(580,left*2+(maxLevel+1)*xGap);
 const height=Math.max(190,top+maxRows*yGap+35);
 const positions={};
 buckets.forEach((items,l)=>{
  items.forEach((state,i)=>{
   positions[state.id]={x:left+l*xGap,y:top+(i-(items.length-1)/2)*yGap+maxRows*yGap/2};
  });
 });
 const root=svg("svg",{viewBox:`0 0 ${width} ${height}`,width:"100%",height:height,role:"img","aria-label":`Diagrama ${type} estilo JFLAP`});
 const defs=svg("defs"),marker=svg("marker",{id:`jflap-arrow-${type}`,markerWidth:8,markerHeight:8,refX:7,refY:3,orient:"auto",markerUnits:"strokeWidth"});
 marker.appendChild(svg("path",{d:"M0,0 L0,6 L8,3 z",fill:"#315f86"}));defs.appendChild(marker);root.appendChild(defs);
 const grouped=groupTransitions(transitions);
 grouped.forEach((edge,index)=>{
  const a=positions[edge.from],b=positions[edge.to];if(!a||!b)return;
  let path,labelX,labelY;
  if(edge.from===edge.to){
   path=`M ${a.x-12} ${a.y-radius+1} C ${a.x-54} ${a.y-76}, ${a.x+54} ${a.y-76}, ${a.x+12} ${a.y-radius+1}`;
   labelX=a.x;labelY=a.y-54;
  }else{
   const dx=b.x-a.x,dy=b.y-a.y;
   const sx=a.x+(dx===0?0:Math.sign(dx)*radius),sy=a.y+(dx===0?Math.sign(dy)*radius:0);
   const ex=b.x-(dx===0?0:Math.sign(dx)*(radius+4)),ey=b.y-(dx===0?Math.sign(dy)*(radius+4):0);
   if(Math.abs(dy)<8){
    path=`M ${sx} ${sy} L ${ex} ${ey}`;
    labelX=(sx+ex)/2;labelY=(sy+ey)/2-10;
   }else{
    const bend=Math.max(22,Math.abs(dy)*.35);
    const midX=(sx+ex)/2;
    path=`M ${sx} ${sy} Q ${midX} ${sy+(dy>0?bend:-bend)} ${ex} ${ey}`;
    labelX=midX;labelY=(sy+ey)/2+(dy>0?bend:-bend)-4;
   }
  }
  root.appendChild(svg("path",{d:path,fill:"none",stroke:"#315f86","stroke-width":1.55,"marker-end":`url(#jflap-arrow-${type})`}));
  const label=edge.symbols.map(s=>s==="ε"?"ε":s===" "?"␠":s).join(", ");
  const txt=svg("text",{x:labelX,y:labelY,"text-anchor":"middle",fill:"#244d70","font-size":9,"font-family":"Arial, sans-serif"});
  txt.textContent=label.length>24?label.slice(0,21)+"…":label;root.appendChild(txt);
 });
 states.forEach(state=>{
  const p=positions[state.id];if(!p)return;
  if(state.id===start){
   root.appendChild(svg("path",{d:`M ${p.x-49} ${p.y} L ${p.x-radius-4} ${p.y}`,fill:"none",stroke:"#315f86","stroke-width":1.6,"marker-end":`url(#jflap-arrow-${type})`}));
   const init=svg("text",{x:p.x-48,y:p.y-12,"text-anchor":"middle",fill:"#315f86","font-size":8});init.textContent="inicio";root.appendChild(init);
  }
  root.appendChild(svg("circle",{cx:p.x,cy:p.y,r:radius,fill:state.accepting?"#e5f8ef":"#edf4fb",stroke:state.accepting?"#0b9b63":"#315f86","stroke-width":1.7}));
  if(state.accepting)root.appendChild(svg("circle",{cx:p.x,cy:p.y,r:radius-4,fill:"none",stroke:"#0b9b63","stroke-width":1.3}));
  const label=svg("text",{x:p.x,y:p.y+3.5,"text-anchor":"middle",fill:"#173c5c","font-size":9,"font-family":"Arial, sans-serif"});label.textContent=state.id;root.appendChild(label);
 });
 return root;
}
function makeTable(headers,rows){const table=document.createElement("table");const thead=document.createElement("thead"),tr=document.createElement("tr");headers.forEach(h=>{const th=document.createElement("th");th.textContent=h;tr.appendChild(th);});thead.appendChild(tr);table.appendChild(thead);const tbody=document.createElement("tbody");rows.forEach(r=>tbody.appendChild(cellRow(r)));table.appendChild(tbody);return table;}
function panel(title,child){const box=document.createElement("div");box.className="automaton-panel";const h=document.createElement("h4");h.textContent=title;box.append(h,child);return box;}
function renderAutomata(r){
 automatas=r.automatas||[];const select=$("selectorAutomata");select.innerHTML="";
 automatas.forEach(a=>{const o=document.createElement("option");o.value=a.campo;o.textContent=a.campo;select.appendChild(o);});
 select.value=automatas.some(a=>a.campo==="DNI")?"DNI":automatas[0]?.campo||"";campoSeleccionado=select.value;renderSelectedAuto();
}
function renderQuintuple(q){
 const rows=[["Q (estados)",`{ ${q.Q.join(", ")} }`],["Σ (alfabeto)",`{ ${q.Sigma.map(x=>x===" "?"␠":x).join(", ")} }`],["δ (transiciones)",`${q.delta.length} transiciones definidas en la tabla completa`],["q₀ (inicial)",q.q0],["F (finales)",`{ ${q.F.join(", ")} }`]];
 return makeTable(["Componente","Valor"],rows);
}
function renderSelectedAuto(){
 const host=$("detalleAutomata");host.innerHTML="";const a=automatas.find(x=>x.campo===campoSeleccionado);if(!a){host.textContent="No hay autómatas disponibles.";return;}
 const er=document.createElement("div");er.className="regex-display";er.innerHTML=`<b>Expresión regular de ${esc(a.campo)}</b><code>${esc(a.regex)}</code>`;host.appendChild(er);
 if(a.error){const p=document.createElement("p");p.textContent=a.error;host.appendChild(p);return;}
 const pair=document.createElement("div");pair.className="automata-pair";
 const nfaGraph=graphFor(a.afnd,"AFND"),dfaGraph=graphFor(a.afd,"AFD");
 pair.appendChild(panel("Autómata Finito No Determinista (AFND)",nfaGraph));pair.appendChild(panel("Autómata Finito Determinista (AFD)",dfaGraph));host.appendChild(pair);
 const nfaRows=(a.afnd.states||[]).flatMap(s=>(s.transitions||[]).map(t=>[s.id,t.symbol,t.to]));
 host.appendChild(panel("Tabla de transiciones del AFND",makeTable(["Estado origen","Símbolo","Estado destino"],nfaRows)));
 host.appendChild(panel("Quíntupla del AFND",renderQuintuple(a.afnd.quintuple)));
 const dfaRows=(a.afd.transitions||[]).map(t=>[t.from,t.symbol,t.to]);
 host.appendChild(panel("Tabla de transiciones del AFD",makeTable(["Estado origen","Símbolo","Estado destino"],dfaRows)));
 host.appendChild(panel("Quíntupla del AFD",renderQuintuple(a.quintuple)));
}
$("selectorAutomata").addEventListener("change",e=>{campoSeleccionado=e.target.value;renderSelectedAuto();$("resultadoSimulacion").textContent="Escribe una cadena para simular.";});
function simulateDFA(){
 const a=automatas.find(x=>x.campo===campoSeleccionado);if(!a||a.error)return;
 const input=$("cadenaSimular").value;let state=a.afd.start,trace=[state],failed=false;
 for(const ch of input){const tr=a.afd.transitions.find(t=>t.from===state&&t.symbol===ch);if(!tr){failed=true;break;}state=tr.to;trace.push(state);}
 const accepted=!failed&&a.afd.final.includes(state);
 $("resultadoSimulacion").textContent=`${accepted?"CADENA ACEPTADA":"CADENA RECHAZADA"} · Recorrido: ${trace.join(" → ")}${failed?" → transición inexistente":""}`;
 $("resultadoSimulacion").className="simulation-result "+(accepted?"good":"bad");
}
$("btnSimular").addEventListener("click",simulateDFA);$("cadenaSimular").addEventListener("keydown",e=>{if(e.key==="Enter")simulateDFA();});
function renderErrors(r){
 const p=$("erroresPanel"),list=$("listaErrores");list.innerHTML="";const errors=r.errores||[];p.classList.toggle("hidden",!errors.length);
 errors.forEach(e=>{const li=document.createElement("li");li.textContent=e;list.appendChild(li);});
}
function renderResult(r){
 ultimo=r;$("resultado").classList.remove("hidden");$("proceso").classList.remove("hidden");
 $("estadoBadge").textContent=r.valido?"Registro médico válido: análisis léxico, sintáctico y semántico completados.":"Registro con errores: revisa las observaciones del compilador.";
 $("estadoBadge").className="result-banner "+(r.valido?"good":"bad");
 $("estadoDescripcion").textContent=r.valido?"La información se encuentra estructurada y lista para revisión o almacenamiento.":"La información contiene campos faltantes, valores inválidos o problemas de estructura.";
 $("totalTokens").textContent=r.total_tokens;$("totalCampos").textContent=`${r.campos_reconocidos}/${r.total_campos}`;$("totalErrores").textContent=r.errores.length;
 $("resultadoJSON").textContent=JSON.stringify(r.datos,null,2);$("jsonProceso").textContent=JSON.stringify(r.datos,null,2);
 $("origenInfo").textContent=mode()==="plantilla"?"Plantilla web":mode()==="archivo"?"Archivo TXT":"DSL ingresado manualmente";
 renderGroups(r);renderSequence(r);renderGrammar(r);renderSemantic(r);renderAutomata(r);renderErrors(r);
}
async function analyze(){
 $("btnAnalizar").disabled=true;$("btnAnalizar").textContent="Analizando...";
 try{const texto=await textoEntrada();if(!texto)throw Error("Ingresa un registro médico.");const res=await fetch("/analizar",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({texto})});const data=await res.json();if(!res.ok)throw Error(data.mensaje||"No se pudo analizar.");renderResult(data);notice("Análisis completado. Revisa las secciones B y C.","success");$("resultado").scrollIntoView({behavior:"smooth",block:"start"});}
 catch(e){notice(e.message,"error");}
 finally{$("btnAnalizar").disabled=false;$("btnAnalizar").textContent="Analizar y compilar registro";}
}
$("btnAnalizar").addEventListener("click",analyze);
$("btnEjemplo").addEventListener("click",()=>{document.querySelector('input[name="modo"][value="dsl"]').checked=true;changeMode();$("codigoDSL").value=EJEMPLO;notice("Ejemplo de registro médico cargado.","success");});
$("btnLimpiar").addEventListener("click",()=>{$("codigoDSL").value="";$("archivoTxt").value="";$("nombreArchivo").textContent="Ningún archivo seleccionado";CAMPOS.forEach(c=>{if($(c))$(c).value="";});$("resultado").classList.add("hidden");$("proceso").classList.add("hidden");ultimo=null;notice("Formulario limpiado.","success");});
$("archivoTxt").addEventListener("change",e=>$("nombreArchivo").textContent=e.target.files[0]?.name||"Ningún archivo seleccionado");
$("btnPDF").addEventListener("click",async()=>{if(!ultimo)return;try{const res=await fetch("/descargar-pdf",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({resultado:ultimo})});if(!res.ok)throw Error("No se pudo generar el PDF.");const blob=await res.blob(),url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="reporte_rulecheck.pdf";a.click();URL.revokeObjectURL(url);}catch(e){notice(e.message,"error");}});
$("btnJSON").addEventListener("click",()=>{if(!ultimo)return;const blob=new Blob([JSON.stringify(ultimo.datos,null,2)],{type:"application/json"}),url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="registro_medico.json";a.click();URL.revokeObjectURL(url);});
changeMode();

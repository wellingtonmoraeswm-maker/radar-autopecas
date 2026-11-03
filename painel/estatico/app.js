"use strict";

// ---------------------------------------------------------------- utilidades
const $ = (sel, raiz = document) => raiz.querySelector(sel);
const $$ = (sel, raiz = document) => [...raiz.querySelectorAll(sel)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const urlSegura = (u) => (/^https?:\/\//i.test(u || "") ? u : "#");
const dataBR = (iso) => (iso ? iso.slice(0, 10).split("-").reverse().join("/") : "—");
const memoria = {
  ler(k, padrao) { try { return localStorage.getItem(k) ?? padrao; } catch { return padrao; } },
  gravar(k, v) { try { localStorage.setItem(k, v); } catch { /* sem armazenamento: segue sem lembrar */ } },
};

const estado = { visao: memoria.ler("radar.visao", "V01"), periodo: memoria.ler("radar.periodo", "semana"), de: "", ate: "", aba: "painel", noticias: [] };

// Modo demonstracao: o mesmo painel le os arquivos exportados (painel/exportar.py) e nao executa acoes.
const ESTATICO = document.body.dataset.modo === "estatico";
const cacheEstatico = {};
const lerEstatico = (nome) => (cacheEstatico[nome] ??= fetch(`dados/${nome}`).then((r) => {
  if (!r.ok) throw new Error(`dados indisponíveis (${nome})`);
  return r.json();
}));
const somarDias = (iso, n) => { const d = new Date(`${iso}T12:00:00Z`); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
async function apiEstatica(caminho) {
  const [rota, qs] = caminho.split("?");
  const q = new URLSearchParams(qs || "");
  const arquivos = { "/api/estado": "estado.json", "/api/indicadores": "indicadores.json", "/api/temas": "temas.json", "/api/fontes": "fontes.json" };
  if (arquivos[rota]) return lerEstatico(arquivos[rota]);
  if (rota === "/api/resumos") {
    const lista = await lerEstatico("resumos.json");
    return q.get("visao") ? lista.filter((r) => r.visao === q.get("visao")) : lista;
  }
  if (rota === "/api/noticias") {
    const d = await lerEstatico(`noticias-${q.get("visao") || "V01"}.json`);
    const base = (await lerEstatico("estado.json")).exportado_em;
    const fim = q.get("de") ? (q.get("ate") || base) : base;
    const inicio = q.get("de") || somarDias(base, -(({ dia: 1, semana: 7, mes: 30, semestre: 182 }[q.get("periodo")] || 7) - 1));
    return { ...d, inicio, fim, noticias: d.noticias.filter((n) => n.data >= inicio && n.data <= fim) };
  }
  throw new Error("indisponível na demonstração");
}

async function api(caminho, corpo) {
  if (ESTATICO) {
    if (corpo !== undefined) throw new Error("Esta ação não está disponível na demonstração.");
    return apiEstatica(caminho);
  }
  const opcoes = corpo === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) };
  const r = await fetch(caminho, opcoes);
  const dados = await r.json().catch(() => ({ erro: `resposta inválida (${r.status})` }));
  if (!r.ok && dados.erro) throw new Error(dados.erro);
  return dados;
}

function consulta() {
  const p = new URLSearchParams({ visao: estado.visao });
  if (estado.periodo === "personalizado" && estado.de) { p.set("de", estado.de); if (estado.ate) p.set("ate", estado.ate); }
  else p.set("periodo", estado.periodo === "personalizado" ? "semana" : estado.periodo);
  return p.toString();
}

function avisar(html, tempo = 6000) {
  const el = $("#aviso");
  el.innerHTML = `<button class="botao fantasma pequeno fechar" type="button">Fechar</button>${html}`;
  el.hidden = false;
  $(".fechar", el).onclick = () => (el.hidden = true);
  clearTimeout(avisar.t);
  if (tempo) avisar.t = setTimeout(() => (el.hidden = true), tempo);
}

const selo = (classe, texto) => `<span class="selo ${classe}">${esc(texto)}</span>`;
const CLASSIF = { risco: ["critico", "Risco"], oportunidade: ["bom", "Oportunidade"], atencao: ["atencao", "Atenção"], neutro: ["neutro", "Informativo"] };

// ---------------------------------------------------------------- estado geral
async function carregarEstado() {
  const e = await api("/api/estado");
  const sel = $("#visao");
  sel.innerHTML = e.visoes.map((v) => `<option value="${esc(v.id)}">${esc(v.nome)} · ${esc(v.usuario)}</option>`).join("");
  if (!e.visoes.some((v) => v.id === estado.visao)) estado.visao = e.visoes[0]?.id;
  sel.value = estado.visao;
  const coleta = e.ultima_coleta ? `última coleta ${dataBR(e.ultima_coleta)} ${e.ultima_coleta.slice(11, 16)}` : "sem coleta ainda";
  const ia = e.ia.provedor ? `IA: ${e.ia.provedor} (${e.ia.modelo})${e.ia.tem_chave === false ? " sem chave" : ""}` : "IA não configurada";
  $("#status-geral").textContent = `${coleta} · ${ia}`;
}

// ---------------------------------------------------------------- indicadores
function sparkline(hist) {
  const L = 200, A = 40, M = 4;
  if (hist.length < 2) return "";
  const vals = hist.map((h) => h.valor);
  const min = Math.min(...vals), max = Math.max(...vals), amp = max - min || 1;
  const pts = hist.map((h, i) => [M + (i * (L - 2 * M)) / (hist.length - 1), A - M - ((h.valor - min) / amp) * (A - 2 * M)]);
  const caminho = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const [ux, uy] = pts[pts.length - 1];
  return `<svg viewBox="0 0 ${L} ${A}" preserveAspectRatio="none" role="img" aria-label="Tendência dos últimos ${hist.length} meses">
    <line class="spark-guia" x1="0" x2="0" y1="0" y2="${A}" visibility="hidden"/>
    <path class="spark-linha" d="${caminho}" vector-effect="non-scaling-stroke"/>
    <circle class="spark-ponto" cx="${ux}" cy="${uy}" r="4" vector-effect="non-scaling-stroke"/>
    <circle class="spark-foco" r="4" visibility="hidden" vector-effect="non-scaling-stroke"/>
    <rect x="0" y="0" width="${L}" height="${A}" fill="transparent" data-pts='${JSON.stringify(pts.map(([x, y]) => [+x.toFixed(1), +y.toFixed(1)]))}'/>
  </svg>`;
}

function ligarTooltips(raiz, inds) {
  const tip = $("#tooltip");
  $$(".kpi", raiz).forEach((cartao, k) => {
    const svg = $("svg", cartao), alvo = svg && $("rect", svg);
    if (!alvo) return;
    const pts = JSON.parse(alvo.dataset.pts), hist = inds[k].historico;
    const guia = $(".spark-guia", svg), foco = $(".spark-foco", svg);
    const mover = (ev) => {
      const caixa = svg.getBoundingClientRect();
      const x = ((ev.clientX - caixa.left) / caixa.width) * 200;
      let i = 0;
      pts.forEach((p, j) => { if (Math.abs(p[0] - x) < Math.abs(pts[i][0] - x)) i = j; });
      guia.setAttribute("x1", pts[i][0]); guia.setAttribute("x2", pts[i][0]); guia.setAttribute("visibility", "visible");
      foco.setAttribute("cx", pts[i][0]); foco.setAttribute("cy", pts[i][1]); foco.setAttribute("visibility", "visible");
      const v = hist[i].valor.toLocaleString("pt-BR", { maximumFractionDigits: inds[k].valor_fmt.includes(",") ? 2 : 0 });
      tip.textContent = `${hist[i].rotulo}: ${v}`;
      tip.hidden = false;
      tip.style.left = `${Math.min(ev.clientX + 12, innerWidth - tip.offsetWidth - 8)}px`;
      tip.style.top = `${ev.clientY - 34}px`;
    };
    const sair = () => { tip.hidden = true; guia.setAttribute("visibility", "hidden"); foco.setAttribute("visibility", "hidden"); };
    alvo.addEventListener("pointermove", mover);
    alvo.addEventListener("pointerleave", sair);
  });
}

async function carregarIndicadores() {
  const inds = await api("/api/indicadores");
  const raiz = $("#kpis");
  if (!inds.length) { raiz.innerHTML = `<div class="vazio">Sem séries coletadas. Use “Atualizar dados”.</div>`; return; }
  raiz.innerHTML = inds.map((i) => `
    <article class="kpi">
      <span class="rotulo">${esc(i.nome)}</span>
      <span class="valor">${esc(i.valor_fmt)}</span>
      <span class="ref">${esc(i.referencia_fmt)} · ${esc(i.unidade)}</span>
      <span class="deltas">
        ${i.var_mes_fmt ? `<span><b>${esc(i.var_mes_fmt)}</b> no mês</span>` : ""}
        ${i.var_ano_fmt ? `<span><b>${esc(i.var_ano_fmt)}</b> em 12 meses</span>` : ""}
      </span>
      ${sparkline(i.historico)}
    </article>`).join("");
  ligarTooltips(raiz, inds);
  $("#kpis-tabela").innerHTML = `<div class="rolagem"><table class="tabela"><thead><tr><th>Indicador</th><th>Valor</th><th>Referência</th><th>No mês</th><th>Em 12 meses</th></tr></thead><tbody>${
    inds.map((i) => `<tr><td>${esc(i.nome)}</td><td class="num">${esc(i.valor_fmt)}</td><td>${esc(i.referencia_fmt)}</td><td class="num">${esc(i.var_mes_fmt || "—")}</td><td class="num">${esc(i.var_ano_fmt || "—")}</td></tr>`).join("")
  }</tbody></table></div>`;
}

// ---------------------------------------------------------------- noticias
function cartaoNoticia(n) {
  const temas = n.temas.map((t) => `<span class="chip">${esc(t.nome)}</span>`).join("");
  const origem = n.origem_nota === "ia" ? "IA" : "regras";
  return `<article class="noticia ${n.do_setor ? "" : "fora"}">
    <div class="nota" title="Nota ${origem}${n.acima_do_corte ? "" : ", abaixo do corte da visão"}">${n.do_setor ? n.nota : "–"}<small>${origem}</small></div>
    <div>
      <a class="titulo" href="${esc(urlSegura(n.url))}" target="_blank" rel="noopener noreferrer">${esc(n.titulo)}</a>
      <div class="meta"><span>${esc(n.fonte)}</span><span>${dataBR(n.data)}${n.data_estimada ? " (coleta)" : ""}</span>
        ${n.do_setor ? "" : selo("neutro", "Fora do setor")}${n.acima_do_corte ? "" : (n.do_setor ? selo("neutro", "Abaixo do corte") : "")}</div>
      ${n.justificativa ? `<p>${esc(n.justificativa)}</p>` : ""}
      ${temas ? `<div class="chips">${temas}</div>` : ""}
    </div>
  </article>`;
}

async function carregarNoticias() {
  const d = await api(`/api/noticias?${consulta()}`);
  estado.noticias = d.noticias;
  const destaques = d.noticias.filter((n) => n.acima_do_corte).slice(0, 5);
  $("#destaque-info").textContent = `${dataBR(d.inicio)} a ${dataBR(d.fim)} · corte ${d.corte}`;
  $("#destaques").innerHTML = destaques.length ? destaques.map(cartaoNoticia).join("")
    : `<div class="vazio">Nenhuma notícia acima do corte da visão neste período.</div>`;
  const temas = new Map();
  d.noticias.forEach((n) => n.temas.forEach((t) => temas.set(t.id, t.nome)));
  const sel = $("#filtro-tema"), atual = sel.value;
  sel.innerHTML = `<option value="">Todos os temas</option>` + [...temas].sort((a, b) => a[1].localeCompare(b[1])).map(([id, nome]) => `<option value="${esc(id)}">${esc(nome)}</option>`).join("");
  sel.value = temas.has(atual) ? atual : "";
  filtrarNoticias();
}

function filtrarNoticias() {
  const busca = $("#busca").value.trim().toLowerCase(), tema = $("#filtro-tema").value;
  const soSetor = $("#so-setor").checked, soCorte = $("#so-corte").checked;
  const lista = estado.noticias.filter((n) => (!soSetor || n.do_setor) && (!soCorte || n.acima_do_corte)
    && (!tema || n.temas.some((t) => t.id === tema)) && (!busca || n.titulo.toLowerCase().includes(busca)));
  $("#noticias-info").textContent = `${lista.length} de ${estado.noticias.length} notícias no período`;
  $("#noticias").innerHTML = lista.length ? lista.map(cartaoNoticia).join("") : `<div class="vazio">Nada com esses filtros.</div>`;
}

// ---------------------------------------------------------------- resumos
function htmlResumo(r) {
  if (!r) return `<div class="vazio">Ainda não há resumo para esta visão. Use “Gerar resumo”.</div>`;
  const c = r.cabecalho, res = r.resumo || {};
  const estadoAud = r.aprovado ? selo("bom", "Auditado: números conferem") : selo("critico", "Bloqueado pelo auditor: não enviar");
  const itens = (res.itens || []).map((it, k) => {
    const [cls, rot] = CLASSIF[it.classificacao] || ["neutro", it.classificacao];
    const fontes = [...new Set((it.refs || []).map((ref) => {
      const f = r.fatos[ref];
      if (!f) return "";
      return f.tipo === "noticia"
        ? `<a href="${esc(urlSegura(f.url))}" target="_blank" rel="noopener noreferrer">${esc(f.titulo)}</a> · ${esc(f.fonte)} · ${esc(f.data)}`
        : `${esc(f.fonte)} · referência ${esc(f.referencia_fmt)}`;
    }))].filter(Boolean).join("<br>");
    return `<div class="item">
      <h4>${k + 1}. ${esc(it.o_que_aconteceu)}</h4>
      ${selo(cls, rot)}
      <dl><dt>O que mudou</dt><dd>${esc(it.o_que_mudou)}</dd>
      <dt>Por que importa</dt><dd>${esc(it.por_que_importa)}</dd>
      <dt>O que acompanhar</dt><dd>${esc(it.o_que_acompanhar)}</dd></dl>
      <p class="fonte">Fonte: ${fontes}</p></div>`;
  }).join("");
  const problemas = r.aprovado ? "" : `<div class="nota-dados"><b>Problemas:</b><ul>${r.problemas.map((p) => `<li>${esc(p)}</li>`).join("")}</ul></div>`;
  return `<div class="meta">${estadoAud}<span>${esc(c.versao)} · ${esc(c.visao)}</span><span>${esc(c.periodo)}</span><span>gerado ${esc(c.gerado_em)}</span></div>
    <p class="manchete">${esc(res.manchete)}</p>${itens}
    <p class="nota-dados"><b>Sobre os dados:</b> ${esc(res.nota_sobre_os_dados)}<br>
    ${esc(c.contagem.acima_do_corte)} notícia(s) acima do corte, de ${esc(c.contagem.do_setor)} do setor. Texto por IA (${esc(c.provedor)}, ${esc(c.modelo)}); interpretações não são fatos.</p>${problemas}`;
}

async function carregarResumos() {
  const lista = await api(`/api/resumos?visao=${encodeURIComponent(estado.visao)}`);
  $("#resumo-atual").innerHTML = htmlResumo(lista[0]);
  $("#historico").innerHTML = lista.length ? lista.map((r, k) => `
    <button type="button" class="historico" data-k="${k}" aria-current="${k === 0}">
      <span>${r.aprovado ? selo("bom", "Auditado") : selo("critico", "Bloqueado")}</span>
      <b>${esc(r.cabecalho.versao)} · ${esc(r.cabecalho.periodo)}</b>
      <small>gerado ${esc(r.cabecalho.gerado_em)}</small>
    </button>`).join("") : `<div class="vazio">Sem resumos ainda.</div>`;
  $("#resumo-escolhido").innerHTML = htmlResumo(lista[0]);
  $$("#historico .historico").forEach((b) => b.addEventListener("click", () => {
    $$("#historico .historico").forEach((x) => x.setAttribute("aria-current", "false"));
    b.setAttribute("aria-current", "true");
    $("#resumo-escolhido").innerHTML = htmlResumo(lista[+b.dataset.k]);
  }));
}

// ---------------------------------------------------------------- fontes
const STATUS_FONTE = { ativa: ["bom", "Ativa"], candidata: ["atencao", "Candidata"], pausada: ["neutro", "Pausada"], quebrada: ["critico", "Quebrada"], descartada: ["neutro", "Descartada"] };
async function carregarFontes() {
  const [fontes, temas] = await Promise.all([api("/api/fontes"), estado.temas ? Promise.resolve(estado.temas) : api("/api/temas")]);
  estado.temas = temas;
  const selTema = $("#tema-fonte");
  if (!selTema.options.length) selTema.innerHTML = temas.map((t) => `<option value="${esc(t.id)}">${esc(t.nome)}</option>`).join("");
  const mostrarExcluidas = $("#mostrar-descartadas").checked;
  const visiveis = fontes.filter((f) => mostrarExcluidas || f.status !== "descartada");
  const conta = (s) => fontes.filter((f) => f.status === s).length;
  $("#fontes-resumo").textContent = `${conta("ativa")} ativas · ${conta("candidata")} candidatas · ${conta("pausada")} pausadas · ${conta("descartada")} excluídas`;
  const acoes = (f) => {
    const b = (status, rotulo, classe = "fantasma") => `<button type="button" class="botao ${classe} pequeno" data-id="${esc(f.id)}" data-status="${status}">${rotulo}</button>`;
    if (f.status === "descartada") return f.conector ? b("ativa", "Reincluir") : "";
    return [f.status === "ativa" ? b("pausada", "Pausar") : "", f.status === "pausada" || (f.status === "quebrada" && f.conector) ? b("ativa", "Reativar") : "",
      b("descartada", "Excluir")].join("");
  };
  $("#fontes").innerHTML = `<thead><tr><th>Id</th><th>Fonte</th><th>Situação</th><th>Tipo</th><th>Escopo</th><th>Confiab.</th><th>Verificação</th><th>Observação</th><th>Ações</th></tr></thead><tbody>${
    visiveis.map((f) => { const [c, t] = STATUS_FONTE[f.status] || ["neutro", f.status];
      return `<tr class="${esc(f.status)}"><td>${esc(f.id)}</td><td><a href="${esc(urlSegura(f.url))}" target="_blank" rel="noopener noreferrer">${esc(f.nome)}</a></td><td>${selo(c, t)}</td><td>${esc(f.tipo)}</td><td>${esc(f.escopo)}</td><td>${esc(f.confiabilidade)}</td><td>${esc(f.ultima_verificacao || "—")}</td><td>${esc(f.observacao)}</td><td class="acoes-linha">${acoes(f)}</td></tr>`; }).join("")
  }</tbody>`;
  $$("#fontes [data-status]").forEach((b) => b.addEventListener("click", async () => {
    const nome = b.closest("tr").children[1].textContent;
    let motivo = "";
    if (b.dataset.status === "descartada") {
      motivo = prompt(`Excluir “${nome}” do Radar?\nA fonte para de ser coletada; o que já foi coletado continua no histórico.\n\nMotivo (opcional):`, "");
      if (motivo === null) return;
    }
    b.disabled = true;
    try {
      await api("/api/fontes/status", { id: b.dataset.id, status: b.dataset.status, motivo });
      await carregarFontes();
    } catch (e) { avisar(`✖ ${esc(e.message)}`, 0); b.disabled = false; }
  }));
}

$("#mostrar-descartadas").addEventListener("change", carregarFontes);

$("#testar-fonte").addEventListener("click", async (ev) => {
  const f = $("#form-fonte"), url = f.url.value.trim(), caixa = $("#resultado-teste"), b = ev.target;
  if (!url) { f.url.reportValidity(); return; }
  b.disabled = true; b.textContent = "Testando…"; $("#fonte-msg").textContent = "";
  try {
    const r = await api("/api/fontes/testar", { url });
    const bloqueado = r.robots.startsWith("BLOQUEADO") || !r.ok;
    caixa.innerHTML = `${bloqueado ? selo("critico", "Não pode ser usada") : r.formato === "rss" ? selo("bom", "Pronta para ativar") : selo("atencao", "Entra como candidata")}
      <p>${esc(r.mensagem)}</p>
      <p class="discreto">robots.txt: ${esc(r.robots)} · formato: ${esc(r.formato || "—")}${r.url_sugerida !== url ? ` · endereço usado: ${esc(r.url_sugerida)}` : ""}</p>
      ${r.exemplos.length ? `<b>Últimos itens:</b><ul>${r.exemplos.map((e) => `<li>${esc(e)}</li>`).join("")}</ul>` : ""}`;
    caixa.hidden = false;
    $("#campos-fonte").hidden = bloqueado;
    if (!bloqueado && !f.nome.value) f.nome.value = new URL(url).hostname.replace(/^www\./, "");
  } catch (e) { caixa.innerHTML = `<p>✖ ${esc(e.message)}</p>`; caixa.hidden = false; }
  b.disabled = false; b.textContent = "Testar";
});

$("#form-fonte").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target, msg = $("#fonte-msg"), dados = Object.fromEntries(new FormData(f));
  msg.textContent = "Incluindo…";
  try {
    const r = await api("/api/fontes/incluir", dados);
    msg.textContent = `✔ ${r.fonte.id} incluída como ${r.fonte.status === "ativa" ? "ATIVA (entra na próxima atualização)" : "candidata (precisa de conector)"}.`;
    f.reset(); $("#campos-fonte").hidden = true; $("#resultado-teste").hidden = true;
    await carregarFontes();
  } catch (e) { msg.textContent = `✖ ${e.message}`; }
});

// ---------------------------------------------------------------- configuracoes
const NOMES_PROV = { gemini: "Google Gemini", anthropic: "Anthropic (Claude)" };
async function carregarConfig(cfg) {
  cfg = cfg || await api("/api/config");
  $("#arquivo-chaves").textContent = cfg.arquivo;
  $("#provedores").innerHTML = cfg.provedores.map((p) => `
    <div class="cartao provedor" data-provedor="${esc(p.id)}">
      <h3>${esc(NOMES_PROV[p.id] || p.id)} ${p.id === cfg.ativo ? selo("bom", "Em uso") : ""}</h3>
      <div class="meta"><span>Chave: ${esc(p.chave)}</span>${p.por_variavel ? "<span>(variável de ambiente)</span>" : ""}</div>
      <label class="campo"><span>Modelo</span>
        <div class="linha"><input type="text" value="${esc(p.modelo)}" data-campo="modelo" spellcheck="false">
        <button type="button" class="botao fantasma pequeno" data-acao="modelo" ${p.tem_chave ? "" : "disabled"}>Salvar</button></div></label>
      <div class="linha">
        <button type="button" class="botao pequeno" data-acao="testar" ${p.tem_chave ? "" : "disabled"}>Testar chave</button>
        ${p.id === cfg.ativo ? "" : `<button type="button" class="botao fantasma pequeno" data-acao="ativar" ${p.tem_chave ? "" : "disabled"}>Usar este</button>`}
      </div>
      <p class="mensagem" role="status"></p>
    </div>`).join("");
  $$("#provedores [data-acao]").forEach((b) => b.addEventListener("click", async () => {
    const cartao = b.closest(".provedor"), provedor = cartao.dataset.provedor, msg = $(".mensagem", cartao);
    b.disabled = true; msg.textContent = "…";
    try {
      if (b.dataset.acao === "testar") { const r = await api("/api/config/testar", { provedor }); msg.textContent = `${r.ok ? "✔" : "✖"} ${r.mensagem}`; }
      if (b.dataset.acao === "ativar") { await carregarConfig((await api("/api/config/ativar", { provedor })).config); carregarEstado(); return; }
      if (b.dataset.acao === "modelo") { await carregarConfig((await api("/api/config/modelo", { provedor, modelo: $("[data-campo=modelo]", cartao).value })).config); carregarEstado(); return; }
    } catch (e) { msg.textContent = `✖ ${e.message}`; }
    b.disabled = false;
  }));
}

$("#form-chave").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target, msg = $("#form-msg"), dados = Object.fromEntries(new FormData(f));
  msg.textContent = "Salvando…";
  try {
    const r = await api("/api/config/chave", dados);
    f.reset();
    await carregarConfig(r.config);
    carregarEstado();
    const t = await api("/api/config/testar", { provedor: dados.provedor });
    msg.textContent = `Chave salva e ativada. Teste: ${t.ok ? "✔" : "✖"} ${t.mensagem}`;
  } catch (e) { msg.textContent = `✖ ${e.message}`; }
});

// ---------------------------------------------------------------- eventos gerais
async function recarregar() {
  const tarefas = [carregarNoticias(), carregarResumos()];
  if (estado.aba === "fontes") tarefas.push(carregarFontes());
  await Promise.all(tarefas).catch((e) => avisar(`Erro ao carregar: ${esc(e.message)}`));
}

function marcarPeriodo() {
  $$(".segmentado button").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.periodo === estado.periodo)));
  $("#datas").hidden = estado.periodo !== "personalizado";
}

$$(".segmentado button").forEach((b) => b.addEventListener("click", () => {
  estado.periodo = b.dataset.periodo; memoria.gravar("radar.periodo", estado.periodo); marcarPeriodo();
  if (estado.periodo !== "personalizado" || estado.de) recarregar();
}));
["#de", "#ate"].forEach((s) => $(s).addEventListener("change", () => { estado.de = $("#de").value; estado.ate = $("#ate").value; if (estado.de) recarregar(); }));
$("#visao").addEventListener("change", (e) => { estado.visao = e.target.value; memoria.gravar("radar.visao", estado.visao); recarregar(); });
["#busca", "#filtro-tema", "#so-setor", "#so-corte"].forEach((s) => $(s).addEventListener("input", filtrarNoticias));

$$(".abas button").forEach((b) => b.addEventListener("click", () => {
  estado.aba = b.dataset.aba;
  $$(".abas button").forEach((x) => x.setAttribute("aria-selected", String(x === b)));
  $$(".aba").forEach((s) => (s.hidden = s.id !== `aba-${estado.aba}`));
  if (estado.aba === "fontes") carregarFontes();
  if (estado.aba === "config") carregarConfig();
}));

$("#atualizar").addEventListener("click", async (ev) => {
  const b = ev.target; b.disabled = true; b.textContent = "Atualizando…";
  avisar("Coletando fontes, classificando e passando pela IA. Pode levar alguns minutos…", 0);
  try {
    const r = await api("/api/atualizar", {});
    const log = r.passos.map((p) => `$ ${p.comando} (código ${p.codigo})\n${p.saida.trim().split("\n").slice(-8).join("\n")}`).join("\n\n");
    avisar(`${r.ok ? "✔ Dados atualizados." : "✖ Alguma etapa falhou."}<pre>${esc(log)}</pre>`, 0);
    await Promise.all([carregarEstado(), carregarIndicadores(), recarregar()]);
  } catch (e) { avisar(`✖ ${esc(e.message)}`, 0); }
  b.disabled = false; b.textContent = "Atualizar dados";
});

$("#gerar").addEventListener("click", async (ev) => {
  const b = ev.target; b.disabled = true; b.textContent = "Gerando…";
  const corpo = { visao: estado.visao, versao: $("#versao").value };
  if (estado.periodo === "personalizado" && estado.de) { corpo.de = estado.de; corpo.ate = estado.ate; } else corpo.periodo = estado.periodo === "personalizado" ? "semana" : estado.periodo;
  try {
    const r = await api("/api/resumo", corpo);
    avisar(r.ok ? "✔ Resumo gerado e aprovado pelo auditor." : `✖ Resumo não aprovado.<pre>${esc(r.saida.split("\n").slice(-10).join("\n"))}</pre>`, r.ok ? 5000 : 0);
    await carregarResumos();
  } catch (e) { avisar(`✖ ${esc(e.message)}`, 0); }
  b.disabled = false; b.textContent = "Gerar resumo";
});

$("#tema").addEventListener("click", () => {
  const raiz = document.documentElement;
  const escuroAgora = raiz.dataset.theme ? raiz.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  raiz.dataset.theme = escuroAgora ? "light" : "dark";
  memoria.gravar("radar.tema", raiz.dataset.theme);
});

(async function iniciar() {
  const tema = memoria.ler("radar.tema", "");
  if (tema) document.documentElement.dataset.theme = tema;
  marcarPeriodo();
  try {
    await carregarEstado();
    await Promise.all([carregarIndicadores(), recarregar()]);
  } catch (e) { avisar(`Não foi possível carregar o painel: ${esc(e.message)}`, 0); }
})();

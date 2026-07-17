import re
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    RICH_OK = True
    console = Console()
except ImportError:
    RICH_OK = False
    console = None

try:
    import whois
    WHOIS_OK = True
except ImportError:
    WHOIS_OK = False

try:
    from ddgs import DDGS
    DDG_OK = True
except ImportError:
    DDG_OK = False

try:
    from groq import Groq
    GROQ_OK = True
except ImportError:
    GROQ_OK = False

GROQ_KEY = os.environ.get("GROQ_API_KEY")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# (url_template, verificar_fn, confiavel)
# confiavel=False: plataforma pode retornar falso positivo
PLATAFORMAS = {
    "GitHub":     ("https://github.com/{}", lambda r: r.status_code == 200 and "Not Found" not in r.text[:800], True),
    "Reddit":     ("https://www.reddit.com/user/{}", lambda r: r.status_code == 200 and "Sorry, nobody" not in r.text, True),
    "HackerNews": ("https://news.ycombinator.com/user?id={}", lambda r: r.status_code == 200 and "No such user" not in r.text, True),
    "Keybase":    ("https://keybase.io/{}", lambda r: r.status_code == 200, True),
    "DEV.to":     ("https://dev.to/{}", lambda r: r.status_code == 200 and "404" not in r.url, True),
    "Twitch":     ("https://www.twitch.tv/{}", lambda r: r.status_code == 200, True),
    "Steam":      ("https://steamcommunity.com/id/{}", lambda r: r.status_code == 200 and "The specified profile could not be found" not in r.text, True),
    "Telegram":   ("https://t.me/{}", lambda r: r.status_code == 200 and "tgme_page_photo" in r.text, True),
    "Linktree":   ("https://linktr.ee/{}", lambda r: r.status_code == 200 and "Uh oh" not in r.text, True),
    "Medium":     ("https://medium.com/@{}", lambda r: r.status_code == 200 and "Page not found" not in r.text, True),
    # Abaixo: exigem login ou retornam 200 mesmo sem perfil
    "Twitter/X":  ("https://twitter.com/{}", lambda r: r.status_code == 200, False),
    "Instagram":  ("https://www.instagram.com/{}/", lambda r: r.status_code == 200, False),
    "TikTok":     ("https://www.tiktok.com/@{}", lambda r: r.status_code == 200 and "Couldn't find" not in r.text, False),
    "YouTube":    ("https://www.youtube.com/@{}", lambda r: r.status_code == 200, False),
    "Pinterest":  ("https://www.pinterest.com/{}/", lambda r: r.status_code == 200, False),
}


def _checar_uma(args):
    plataforma, url_template, verificar, confiavel, username = args
    url = url_template.format(username)
    try:
        r = requests.get(url, headers=HEADERS, timeout=6, allow_redirects=True)
        encontrado = verificar(r)
    except Exception:
        encontrado = False
    return {"plataforma": plataforma, "url": url, "encontrado": encontrado, "confiavel": confiavel}


def checar_username(username):
    tarefas = [(plat, url, fn, conf, username) for plat, (url, fn, conf) in PLATAFORMAS.items()]
    resultados = []

    if RICH_OK:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]  Verificando plataformas..."),
            BarColumn(bar_width=30),
            TaskProgressColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("", total=len(tarefas))
            with ThreadPoolExecutor(max_workers=8) as ex:
                futures = {ex.submit(_checar_uma, t): t[0] for t in tarefas}
                for fut in as_completed(futures):
                    resultados.append(fut.result())
                    progress.advance(task)
    else:
        with ThreadPoolExecutor(max_workers=8) as ex:
            resultados = list(ex.map(_checar_uma, tarefas))

    resultados.sort(key=lambda x: (not x["encontrado"], not x["confiavel"], x["plataforma"]))
    return resultados


def mostrar_tabela_username(resultados):
    encontrados = [r for r in resultados if r["encontrado"]]

    if RICH_OK:
        table = Table(
            box=box.ROUNDED,
            border_style="bright_black",
            show_header=True,
            header_style="bold dim",
            expand=False,
        )
        table.add_column("Plataforma", style="bold", min_width=12)
        table.add_column("Status", min_width=16)
        table.add_column("URL", overflow="fold", max_width=55)

        for r in resultados:
            if r["encontrado"]:
                status = Text("ENCONTRADO" if r["confiavel"] else "ENCONTRADO ?", style="bold green" if r["confiavel"] else "bold yellow")
                table.add_row(r["plataforma"], status, f"[cyan]{r['url']}[/cyan]")
            else:
                table.add_row(r["plataforma"], Text("--", style="dim"), Text(r["url"], style="dim"))

        console.print(table)
        console.print(f"  [bold green]{len(encontrados)} perfil(is) encontrado(s)[/bold green]  [dim]({len(resultados) - len(encontrados)} sem perfil)[/dim]\n")
    else:
        for r in resultados:
            print(f"  {r['plataforma']:<14} {'ENCONTRADO' if r['encontrado'] else '--'}")


def buscar_mencoes(query, max_resultados=10):
    if not DDG_OK:
        return []
    resultados = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_resultados):
                resultados.append({
                    "titulo": r.get("title", ""),
                    "url": r.get("href", ""),
                    "descricao": r.get("body", ""),
                })
    except Exception:
        pass
    return resultados


def analisar_dominio(dominio):
    info = {}

    if WHOIS_OK:
        try:
            w = whois.whois(dominio)
            info["Registrador"] = w.registrar or "?"
            criado = w.creation_date
            info["Criado em"] = str(criado[0] if isinstance(criado, list) else criado)
            expira = w.expiration_date
            info["Expira em"] = str(expira[0] if isinstance(expira, list) else expira)
            info["Organizacao"] = w.org or w.name or "Nao disponivel"
            info["Pais"] = w.country or "?"
        except Exception:
            info["WHOIS"] = "Nao disponivel"

    for protocolo in ["https", "http"]:
        try:
            r = requests.get(f"{protocolo}://{dominio}", headers=HEADERS, timeout=8)
            info["HTTPS"] = "Sim" if protocolo == "https" else "Nao"
            info["Status HTTP"] = str(r.status_code)
            info["Servidor"] = r.headers.get("Server", "?")
            info["Powered-By"] = r.headers.get("X-Powered-By", "?")
            if "wp-content" in r.text:
                info["CMS"] = "WordPress"
            elif "cdn.shopify" in r.text:
                info["CMS"] = "Shopify"
            elif "drupal" in r.text.lower():
                info["CMS"] = "Drupal"
            else:
                info["CMS"] = "?"
            break
        except Exception:
            continue

    return info


def analisar_com_ia(dados):
    if not GROQ_OK or not GROQ_KEY:
        return None

    alvo = dados.get("alvo", "")
    encontrados = [r for r in dados.get("username", []) if r["encontrado"]]
    mencoes = dados.get("mencoes", [])
    dominio_info = dados.get("dominio", {})

    partes = [f"Alvo: {alvo}"]

    if encontrados:
        conf = [r["plataforma"] for r in encontrados if r["confiavel"]]
        incertos = [r["plataforma"] for r in encontrados if not r["confiavel"]]
        if conf:
            partes.append(f"Perfis confirmados: {', '.join(conf)}")
        if incertos:
            partes.append(f"Perfis possivelmente presentes: {', '.join(incertos)}")

    if mencoes:
        titulos = "\n".join(f"- {m['titulo']}" for m in mencoes[:6] if m["titulo"])
        partes.append(f"Mencoes na web:\n{titulos}")

    if dominio_info:
        dom = ", ".join(f"{k}: {v}" for k, v in dominio_info.items())
        partes.append(f"Dominio: {dom}")

    contexto = "\n".join(partes)

    prompt = f"""Voce e um analista de OSINT. Com base nos dados abaixo, escreva uma analise em portugues brasileiro com 3 paragrafos:
1. Perfil da presenca digital do alvo
2. Pontos de atencao ou padroes identificados
3. Conclusao geral e nivel de exposicao online

Seja objetivo, profissional e direto. Nao repita os dados brutos.

DADOS:
{contexto}

ANALISE:"""

    try:
        client = Groq(api_key=GROQ_KEY)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        if RICH_OK:
            console.print(f"  [yellow]Erro na analise IA: {e}[/yellow]")
        return None


def gerar_relatorio(dados, agora, analise_ia=None):
    alvo = dados.get("alvo", "")
    username_resultados = dados.get("username", [])
    mencoes = dados.get("mencoes", [])
    dominio_info = dados.get("dominio", {})

    encontrados = [r for r in username_resultados if r["encontrado"]]
    nao_encontrados = [r for r in username_resultados if not r["encontrado"]]

    cards_encontrados = "".join(
        f'<a href="{r["url"]}" target="_blank" class="plat-card {"found" if r["confiavel"] else "uncertain"}">'
        f'<span class="dot {"green" if r["confiavel"] else "yellow"}"></span>{r["plataforma"]}'
        f'{"" if r["confiavel"] else "<span class=warn> ?</span>"}</a>'
        for r in encontrados
    )
    cards_nao = "".join(
        f'<span class="plat-card notfound"><span class="dot gray"></span>{r["plataforma"]}</span>'
        for r in nao_encontrados
    )
    mencoes_html = "".join(
        f'<div class="mencao"><a href="{m["url"]}" target="_blank">{m["titulo"] or m["url"]}</a>'
        f'<p>{(m["descricao"][:140] + "...") if len(m["descricao"]) > 140 else m["descricao"]}</p></div>'
        for m in mencoes
    ) or '<p class="vazio">Nenhuma mencao encontrada.</p>'

    dominio_html = "".join(
        f'<div class="info-row"><span class="key">{k}</span><span class="val">{v}</span></div>'
        for k, v in dominio_info.items()
    ) or '<p class="vazio">Nenhum dominio analisado.</p>'

    ia_section = ""
    if analise_ia:
        paragrafos = "".join(f"<p>{p.strip()}</p>" for p in analise_ia.split("\n") if p.strip())
        ia_section = f"""
<div class="section ia-section">
  <h2>Analise por IA <span class="badge ai">Groq · Llama 3</span></h2>
  <div class="divider"></div>
  <div class="ia-texto">{paragrafos}</div>
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>OSINT - {alvo}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',sans-serif;background:#080b12;color:#e0e0e0;padding:40px;line-height:1.5}}
  a{{color:inherit;text-decoration:none}}
  h1{{color:#fff;font-size:22px;font-weight:700}}
  h2{{font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:#555;margin-bottom:16px}}
  .meta{{color:#444;font-size:12px;margin:4px 0 36px}}
  .meta strong{{color:#aaa}}
  .stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:28px}}
  .stat{{background:#10131d;border-radius:12px;padding:20px 24px;border:1px solid #1a1d2a}}
  .stat .num{{font-size:32px;font-weight:700;color:#fff}}
  .stat .lbl{{font-size:12px;color:#555;margin-top:2px}}
  .section{{background:#10131d;border-radius:12px;padding:24px;margin-bottom:20px;border:1px solid #1a1d2a}}
  .ia-section{{border-color:#312e81}}
  .ia-texto p{{font-size:14px;color:#c7c7d4;line-height:1.8;margin-bottom:12px}}
  .ia-texto p:last-child{{margin-bottom:0}}
  .plat-grid{{display:flex;flex-wrap:wrap;gap:10px}}
  .plat-card{{display:inline-flex;align-items:center;gap:8px;padding:7px 14px;border-radius:8px;font-size:13px}}
  .plat-card.found{{background:#0a1f12;color:#4ade80;border:1px solid #14532d}}
  .plat-card.found:hover{{background:#14532d}}
  .plat-card.uncertain{{background:#1a1400;color:#facc15;border:1px solid #713f12}}
  .plat-card.uncertain:hover{{background:#2d1f00}}
  .plat-card.notfound{{background:#111318;color:#444;border:1px solid #1a1d2a}}
  .dot{{width:7px;height:7px;border-radius:50%;flex-shrink:0}}
  .dot.green{{background:#4ade80}}
  .dot.yellow{{background:#facc15}}
  .dot.gray{{background:#2a2d3a}}
  .warn{{font-size:10px;opacity:0.6}}
  .badge{{display:inline-block;padding:2px 10px;border-radius:20px;font-size:10px;font-weight:700;margin-left:8px;vertical-align:middle}}
  .badge.g{{background:#14532d;color:#4ade80}}
  .badge.d{{background:#1f2937;color:#4b5563}}
  .badge.ai{{background:#1e1b4b;color:#a5b4fc}}
  .mencao{{padding:14px 0;border-bottom:1px solid #1a1d2a}}
  .mencao:last-child{{border-bottom:none}}
  .mencao a{{color:#60a5fa;font-size:14px;font-weight:500}}
  .mencao a:hover{{text-decoration:underline}}
  .mencao p{{color:#555;font-size:12px;margin-top:5px}}
  .info-row{{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid #1a1d2a;font-size:13px}}
  .info-row:last-child{{border-bottom:none}}
  .key{{color:#555}}
  .val{{color:#e0e0e0;text-align:right;max-width:70%}}
  .vazio{{color:#333;font-size:13px}}
  .header{{display:flex;align-items:center;gap:10px;margin-bottom:4px}}
  .pulse{{width:9px;height:9px;border-radius:50%;background:#f59e0b}}
  .divider{{height:1px;background:#1a1d2a;margin-bottom:18px}}
  .legend{{font-size:11px;color:#444;margin-top:14px}}
  .legend span{{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;vertical-align:middle}}
</style>
</head>
<body>
<div class="header"><div class="pulse"></div><h1>Relatorio OSINT</h1></div>
<p class="meta">Alvo: <strong>{alvo}</strong> &nbsp;·&nbsp; Gerado em: {agora}</p>

<div class="stats">
  <div class="stat"><div class="num" style="color:#4ade80">{len(encontrados)}</div><div class="lbl">Perfis encontrados</div></div>
  <div class="stat"><div class="num">{len(nao_encontrados)}</div><div class="lbl">Plataformas sem perfil</div></div>
  <div class="stat"><div class="num" style="color:#60a5fa">{len(mencoes)}</div><div class="lbl">Mencoes na web</div></div>
</div>

{ia_section}

<div class="section">
  <h2>Perfis Ativos <span class="badge g">{len(encontrados)} encontrado(s)</span></h2>
  <div class="divider"></div>
  <div class="plat-grid">{cards_encontrados or '<p class="vazio">Nenhum perfil encontrado.</p>'}</div>
  <p class="legend"><span style="background:#facc15"></span>Amarelo = pode ser falso positivo (plataforma exige login para confirmar)</p>
</div>

<div class="section">
  <h2>Sem Perfil <span class="badge d">{len(nao_encontrados)}</span></h2>
  <div class="divider"></div>
  <div class="plat-grid">{cards_nao}</div>
</div>

<div class="section">
  <h2>Mencoes Publicas (DuckDuckGo)</h2>
  <div class="divider"></div>
  {mencoes_html}
</div>

<div class="section">
  <h2>Analise de Dominio</h2>
  <div class="divider"></div>
  {dominio_html}
</div>
</body>
</html>"""

    nome = f"osint_{re.sub(r'[^a-zA-Z0-9]', '_', alvo)}_{agora.replace('/', '').replace(' ', '_').replace(':', '')}.html"
    with open(nome, "w", encoding="utf-8") as f:
        f.write(html)
    return nome


def investigar():
    if RICH_OK:
        console.print()
        console.print(Panel.fit(
            "[bold cyan]AGENTE OSINT[/bold cyan]  [dim]v2.0[/dim]",
            border_style="cyan",
            padding=(0, 3),
        ))
        if GROQ_OK and GROQ_KEY:
            console.print("  [dim green]IA ativa (Groq)[/dim green]\n")
        elif GROQ_OK and not GROQ_KEY:
            console.print("  [dim yellow]IA desativada — defina GROQ_API_KEY para ativar[/dim yellow]\n")
        console.print()
        alvo = console.input("[bold white]Alvo (nome ou empresa):[/bold white] ").strip()
        username = console.input("[dim]Username a verificar (Enter para pular):[/dim] ").strip()
        dominio = console.input("[dim]Dominio ex: empresa.com (Enter para pular):[/dim] ").strip()
        console.print()
    else:
        print("\n=== AGENTE OSINT v2.0 ===\n")
        alvo = input("Alvo (nome ou empresa): ").strip()
        username = input("Username (Enter para pular): ").strip()
        dominio = input("Dominio (Enter para pular): ").strip()

    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    dados = {"alvo": alvo, "username": [], "mencoes": [], "dominio": {}}

    if username:
        if RICH_OK:
            console.print(f"[bold cyan][1/3][/bold cyan] Verificando [bold]@{username}[/bold] em {len(PLATAFORMAS)} plataformas...")
            console.print()
        else:
            print(f"\n[1/3] Verificando @{username}...")
        dados["username"] = checar_username(username)
        mostrar_tabela_username(dados["username"])

    if RICH_OK:
        console.print(f"[bold cyan][2/3][/bold cyan] Buscando mencoes de [bold]{alvo}[/bold]...")
    else:
        print(f"[2/3] Buscando mencoes...")
    dados["mencoes"] = buscar_mencoes(alvo)
    if RICH_OK:
        console.print(f"  [green]{len(dados['mencoes'])} mencao(oes) encontrada(s)[/green]\n")
    else:
        print(f"  -> {len(dados['mencoes'])} mencao(oes)\n")

    if dominio:
        if RICH_OK:
            console.print(f"[bold cyan][3/3][/bold cyan] Analisando [bold]{dominio}[/bold]...")
        else:
            print(f"[3/3] Analisando {dominio}...")
        dados["dominio"] = analisar_dominio(dominio)
        if RICH_OK:
            console.print("  [green]Concluido[/green]\n")
        else:
            print("  -> Concluido\n")

    analise_ia = None
    if GROQ_OK and GROQ_KEY:
        if RICH_OK:
            console.print("[bold cyan][IA][/bold cyan] Gerando analise com Groq...")
        else:
            print("[IA] Gerando analise...")
        analise_ia = analisar_com_ia(dados)
        if analise_ia and RICH_OK:
            console.print(Panel(
                analise_ia,
                title="[bold]Analise IA[/bold]",
                border_style="blue",
                padding=(1, 2),
            ))

    arquivo = gerar_relatorio(dados, agora, analise_ia)

    if RICH_OK:
        console.print(Panel(
            f"[bold green]Relatorio salvo:[/bold green]\n[cyan]{arquivo}[/cyan]\n\n[dim]Abra no navegador para visualizar.[/dim]",
            border_style="green",
            padding=(1, 2),
        ))
    else:
        print(f"\nRelatorio: {arquivo}\nAbra no navegador para visualizar.\n")


investigar()

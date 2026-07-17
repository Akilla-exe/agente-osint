# Agente OSINT

Ferramenta de Open Source Intelligence (OSINT) com análise por IA. Dado um nome, empresa ou username, o agente coleta automaticamente dados públicos de múltiplas fontes e gera um relatório HTML.

## O que faz

- Verifica presença de um username em **15 plataformas** (GitHub, Reddit, Twitch, Steam, Telegram e mais)
- Busca **menções públicas** na web via DuckDuckGo
- Analisa **domínios** via WHOIS — registrador, data de criação, servidor, CMS
- Gera **relatório HTML** com dark theme, links clicáveis e badges por categoria
- **Análise por IA** (Groq + Llama 3) que interpreta os dados e gera um resumo profissional

## Tecnologias

- Python 3
- [Requests](https://pypi.org/project/requests/)
- [Rich](https://pypi.org/project/rich/) — terminal visual com tabelas e progress bar
- [DDGS](https://pypi.org/project/ddgs/) — busca DuckDuckGo sem API
- [Python-Whois](https://pypi.org/project/python-whois/) — análise de domínios
- [Groq](https://pypi.org/project/groq/) — LLM para análise de inteligência
- `concurrent.futures` — verificação paralela de plataformas

## Como usar

```bash
# Instalar dependências
pip install requests rich ddgs python-whois groq

# (Opcional) Configurar chave Groq para análise por IA
# Windows PowerShell:
[System.Environment]::SetEnvironmentVariable("GROQ_API_KEY", "sua_key", "User")

# Executar
python osint_agente.py
```

O agente vai perguntar:
1. Nome ou empresa alvo
2. Username a verificar (opcional)
3. Domínio a analisar, ex: `empresa.com` (opcional)

O relatório HTML é salvo automaticamente na pasta atual.

## Exemplo de saída

```
=== AGENTE OSINT v2.0 ===

[1/3] Verificando @nubank em 15 plataformas...
  GitHub        ENCONTRADO
  Reddit        ENCONTRADO
  Medium        ENCONTRADO
  Twitter/X     ENCONTRADO ?
  ...
  11 perfil(is) encontrado(s)

[2/3] Buscando menções de 'Nubank'...
  10 menção(ões) encontrada(s)

[3/3] Analisando nubank.com.br...
  Concluído

[IA] Gerando análise com Groq...
  [análise em linguagem natural gerada pelo Llama 3]

Relatório salvo: osint_Nubank_17072026_0407.html
```

> Perfis marcados com `?` podem ser falsos positivos — essas plataformas exigem login para confirmar a existência do perfil.

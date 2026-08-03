"""
Pipeline principal.

Uso:
    python main.py                 # roda tudo (workana + 99freelas)
    python main.py --plataforma workana
    python main.py --min-score 40
    python main.py --revisar       # só mostra propostas já geradas, sem raspar de novo

Antes da primeira vez, rode o login manual de cada plataforma (ver README.md).
"""
import argparse
import time
import os
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

import db
from matcher import load_profile, filter_relevant
from ai_engine import analyze_project
from scrapers import scrape_workana, scrape_99freelas, scrape_freelancer

load_dotenv()
console = Console()


def run_pipeline(plataformas: list[str], min_score: float):
    db.init_db()
    profile = load_profile()

    all_projects = []
    if "workana" in plataformas:
        console.print("[bold cyan]→ Raspando Workana...[/bold cyan]")
        all_projects += scrape_workana()
    if "99freelas" in plataformas:
        console.print("[bold cyan]→ Raspando 99Freelas...[/bold cyan]")
        all_projects += scrape_99freelas()
    if "freelancer" in plataformas:
        console.print("[bold cyan]→ Raspando Freelancer.com...[/bold cyan]")
        all_projects += scrape_freelancer()

    console.print(f"[dim]{len(all_projects)} projetos coletados no total[/dim]")

    relevant = filter_relevant(all_projects, profile, min_score=min_score, only_free_to_bid=True)
    console.print(f"[bold green]{len(relevant)} projetos relevantes e gratuitos para propor[/bold green]\n")

    novos = 0
    for score, project in relevant:
        if db.project_exists(project.id):
            continue

        db.insert_project({
            "id": project.id,
            "platform": project.platform,
            "title": project.title,
            "url": project.url,
            "description": project.description,
            "is_free_to_bid": int(project.is_free_to_bid),
            "match_score": score,
        })

        console.print(f"[yellow]Analisando com IA:[/yellow] {project.title[:70]}")
        try:
            result = analyze_project(project, profile)
        except Exception as e:
            console.print(f"[red]Erro na análise de IA: {e}[/red]")
            continue

        if not result.get("vale_a_pena", True):
            db.mark_status(project.id, "descartado")
            continue

        db.save_ai_result(
            project.id,
            result.get("proposta_texto", ""),
            result.get("valor_sugerido_brl", 0),
            result.get("estimativa_horas", 0),
            result.get("motivo_curto", ""),
        )
        novos += 1
        time.sleep(1)  # não estourar rate limit do Groq

    console.print(f"\n[bold]{novos} propostas novas geradas.[/bold] Use --revisar para ver.")


def show_pending():
    rows = db.list_pending()
    if not rows:
        console.print("[dim]Nenhuma proposta pendente de revisão.[/dim]")
        return

    table = Table(title="Propostas geradas - aguardando revisão")
    table.add_column("Score", justify="right")
    table.add_column("Plataforma")
    table.add_column("Título")
    table.add_column("Valor sugerido (R$)", justify="right")
    table.add_column("Horas est.", justify="right")

    for r in rows:
        table.add_row(
            str(r["match_score"]),
            r["platform"],
            r["title"][:60],
            f"{r['suggested_price_brl']:.0f}",
            str(r["estimated_hours"]),
        )
    console.print(table)

    for r in rows:
        console.print(Panel(
            r["proposal_text"],
            title=f"[bold]{r['title'][:80]}[/bold]\n{r['url']}",
            subtitle=f"R$ {r['suggested_price_brl']:.0f} · {r['estimated_hours']}h · {r['ai_reasoning']}",
        ))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--plataforma", choices=["workana", "99freelas", "freelancer", "todas"], default="todas")
    parser.add_argument("--min-score", type=float, default=25.0)
    parser.add_argument("--revisar", action="store_true", help="Só mostra propostas já geradas")
    args = parser.parse_args()

    if args.revisar:
        show_pending()
    else:
        plataformas = ["workana", "99freelas", "freelancer"] if args.plataforma == "todas" else [args.plataforma]
        run_pipeline(plataformas, args.min_score)

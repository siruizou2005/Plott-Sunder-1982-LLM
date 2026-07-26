"""Command line interface.

    ps1982 validate --scenario ...   render prompts + params, no API calls
    ps1982 run      --scenario ...   run one or more sessions
    ps1982 metrics  --run  ...       compute the post-hoc metrics for a log
    ps1982 summary  --run  ...       print the headline numbers
"""

from __future__ import annotations

import datetime as dt
import json
import signal
import threading
import os
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .config import load_config
from .engine import Engine, write_checkpoint
from .events import EventStream, FanoutSink, JsonlEventSink, read_events
from .metrics import compute_from_file, write_metrics
from .metrics import _benchmarks

app = typer.Typer(add_completion=False, help="Plott & Sunder (1982) Market 3 replication.")
console = Console()

RUNS = Path("runs")


def _run_dir(name: str) -> Path:
    d = RUNS / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _stamp() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")


@app.command()
def validate(scenario: str = typer.Option(..., "--scenario", "-s"),
             seat: str = typer.Option("S01", "--seat"),
             show_prompt: bool = typer.Option(False, "--show-prompt")) -> None:
    """Check a scenario and render one seat's prompts. Makes no API calls."""
    cfg = load_config(scenario)
    mkt = cfg.market_spec
    seq = cfg.sequence
    console.print(f"[bold]scenario[/bold] {scenario}")
    console.print(f"  market={mkt.number}  investors={mkt.n_agents}  "
                  f"states={'/'.join(mkt.states)}  cage={mkt.bingo_total} balls"
                  + ("  [dim]imperfect clue: 10-draw sample[/dim]" if mkt.imperfect else ""))
    console.print(f"  run_name={cfg.run_name}  seed={cfg.seed}  sessions={cfg.sessions}  "
                  f"periods={cfg.n_periods}  rounds/period={cfg.max_rounds_per_period}")
    console.print(f"  sequence={seq.name}  [dim]{seq.note}[/dim]")
    console.print(f"  rules={cfg.rules.model_dump()}")

    t = Table("period", "state", "info", "PI", "RE", "separating", "RE value", "no-trade value")
    for i in range(cfg.n_periods):
        st, info = seq.states[i], seq.info[i]
        th = mkt.theory_at(*(info, st))[0]
        b = _benchmarks(mkt, info, st)
        t.add_row(str(i + 1), st, info, str(th["PI"]), str(th["RE"]),
                  "yes" if th["PI"] != th["RE"] else "-",
                  f"{b['re']:,.0f}", f"{b['no_trade']:,.0f}")
    console.print(t)

    t2 = Table("seat", "type", *[f"d({x})" for x in mkt.states], "prior EV",
               "agent kind")
    for s in mkt.seats:
        d = mkt.dividends[mkt.seat_type[s]]
        t2.add_row(s, mkt.seat_type[s], *[str(d[x]) for x in mkt.states],
                   f"{mkt.prior_ev[mkt.seat_type[s]]:.0f}", cfg.spec_for(s).kind)
    console.print(t2)

    from .prompts import system_prompt
    sp = system_prompt(seat, cfg.rules, cfg.market_spec)
    leaks = [w for w in ("probability", "Probability", "rational expectation",
                         "equilibrium") if w in sp]
    if leaks:
        console.print(f"[red]PROMPT LEAK: system prompt contains {leaks}[/red]")
    else:
        console.print("[green]system prompt clean[/green] "
                      "(no 'probability' / 'equilibrium' language, no theory values)")
    console.print(f"  system prompt for {seat}: {len(sp):,} chars")
    if show_prompt:
        console.print("\n" + sp)


def _truncate_to_checkpoint(log_path: Path, next_event_id: int) -> int:
    """Drop everything the checkpoint does not account for, before appending to the log.

    The checkpoint is written the instant a period settles, so `next_event_id` is exactly
    the boundary of what that period committed. Anything past it is one of two things, and
    both must go:

      * a period that was killed half-way — resuming re-runs it from the start, and leaving
        the abandoned attempt behind would double-count its trades in the metrics, which
        read the log rather than the engine;
      * a `session_end` from a run that actually finished, whose id the resumed leg would
        otherwise reuse.

    Rewrites via a temp file and rename, so an interruption here cannot leave a half-written
    log where a complete one used to be.
    """
    if not log_path.exists():
        return 0
    kept, dropped = [], 0
    with open(log_path, "r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                if json.loads(line)["event_id"] < next_event_id:
                    kept.append(line)
                else:
                    dropped += 1
            except json.JSONDecodeError:
                dropped += 1          # a torn final line from a hard kill
    if dropped:
        tmp = log_path.with_suffix(".jsonl.tmp")
        tmp.write_text("".join(kept), encoding="utf-8")
        os.replace(tmp, log_path)
        console.print(f"  [dim]dropped {dropped} event(s) past the checkpoint[/dim]")
    return dropped


def _write_meta(path, *, scenario, cfg, stamp, status, summaries) -> None:
    """Written at START and rewritten after every period.

    It used to be written only once, after everything finished, so a run that was killed
    left a log with no configuration snapshot beside it — exactly the case where you most
    need to know what produced it. ``status`` says whether the run is still going.
    """
    meta = {"scenario": scenario, "run_name": cfg.run_name, "stamp": stamp,
            "status": status,
            "config": json.loads(cfg.model_dump_json()),
            "sequence": {"name": cfg.sequence.name, "states": list(cfg.sequence.states),
                         "info": list(cfg.sequence.info), "note": cfg.sequence.note},
            "summaries": summaries,
            "totals": {
                "calls": sum(s["calls"] for s in summaries),
                "cost_usd": round(sum(s["cost_usd"] for s in summaries), 4),
                "wall_clock_s": round(sum(s["wall_clock_s"] for s in summaries), 1)}}
    write_checkpoint(str(path), meta)      # same atomic tmp+rename


@app.command()
def run(scenario: str = typer.Option(..., "--scenario", "-s"),
        sessions: int | None = typer.Option(None, "--sessions"),
        periods: int | None = typer.Option(None, "--periods"),
        run_name: str | None = typer.Option(None, "--run-name"),
        seed: int | None = typer.Option(None, "--seed"),
        resume: bool = typer.Option(False, "--resume",
                                    help="continue the newest interrupted run of this name")
        ) -> None:
    """Run the experiment and write runs/<run_name>/<timestamp>.jsonl."""
    cfg = load_config(scenario)
    if sessions is not None:
        cfg.sessions = sessions
    if periods is not None:
        cfg.periods = periods
    if run_name:
        cfg.run_name = run_name
    if seed is not None:
        cfg.seed = seed

    d = _run_dir(cfg.run_name)
    ckpt = None
    if resume:
        cands = sorted(d.glob("*.checkpoint.json"))
        if not cands:
            raise typer.BadParameter(f"nothing to resume in {d}")
        ckpt = json.loads(cands[-1].read_text(encoding="utf-8"))
        stamp = cands[-1].name[: -len(".checkpoint.json")]
        console.print(f"[bold]resume[/bold] {cfg.run_name}/{stamp} "
                      f"from period {ckpt['completed_periods'] + 1}")
    else:
        stamp = _stamp()

    log_path = d / f"{stamp}.jsonl"
    meta_path = d / f"{stamp}.meta.json"
    ckpt_path = d / f"{stamp}.checkpoint.json"
    (RUNS / ".current").write_text(f"{cfg.run_name}/{stamp}", encoding="utf-8")

    if ckpt is not None:
        _truncate_to_checkpoint(log_path, ckpt["next_event_id"])

    # Ids continue from where the interrupted run stopped; the sink opens in append mode.
    stream = EventStream(FanoutSink([JsonlEventSink(str(log_path))]),
                         start_id=(ckpt or {}).get("next_event_id", 0))
    console.print(f"[bold]run[/bold] {cfg.run_name} -> {log_path}")
    console.print(f"  sequence={cfg.sequence.name}  sessions={cfg.sessions}  "
                  f"periods={cfg.n_periods}  llm={'yes' if cfg.uses_llm else 'no (offline)'}")

    summaries: list = []
    _write_meta(meta_path, scenario=scenario, cfg=cfg, stamp=stamp,
                status="running", summaries=summaries)

    # Cooperative stop. A signal cannot interrupt a blocking call inside the broadcast
    # thread pool, which is why plain Ctrl-C did not stop a run; a flag checked at each
    # period boundary does, and it stops where a checkpoint has just been written so the
    # run is resumable. A second signal gives up on that and exits now.
    stop = threading.Event()

    def _on_signal(signum, _frame):
        if stop.is_set():
            console.print("[red]second signal — exiting now; "
                          "resume from the last completed period[/red]")
            raise SystemExit(130)
        stop.set()
        console.print("[yellow]stopping after the current period finishes "
                      "(signal again to stop immediately)[/yellow]")

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _on_signal)

    def checkpoint(eng) -> None:
        write_checkpoint(str(ckpt_path), eng.snapshot())
        _write_meta(meta_path, scenario=scenario, cfg=cfg, stamp=stamp,
                    status="running", summaries=summaries)
        console.print(f"    period {eng.completed_periods}/{cfg.n_periods} settled "
                      f"· {eng.calls} calls · ${eng.usage.cost_usd(cfg.pricing):.3f}")

    interrupted = False
    try:
        for sid in range(cfg.sessions):
            eng = Engine(cfg, stream, session=sid, resume=ckpt if sid == 0 else None)
            eng.on_period_done = checkpoint
            console.print(f"  session {sid + 1}/{cfg.sessions} ...")
            s = eng.run_session(stop=stop)
            if s is None:                       # stopped on a period boundary
                interrupted = True
                break
            summaries.append(s)
            console.print(f"    done in {s['wall_clock_s']}s, {s['calls']} calls, "
                          f"${s['cost_usd']}")
    except KeyboardInterrupt:
        interrupted = True
        console.print("[yellow]interrupted; the log up to this point is valid[/yellow]")
    finally:
        stream.close()
        _write_meta(meta_path, scenario=scenario, cfg=cfg, stamp=stamp,
                    status="interrupted" if interrupted else "done", summaries=summaries)

    if interrupted:
        console.print(f"[yellow]resume with:[/yellow] python -m ps1982 run "
                      f"-s {scenario} --run-name {cfg.run_name} --resume")
    out = write_metrics(str(log_path))
    console.print(f"  metrics -> {out}")
    summary(str(log_path))


@app.command()
def metrics(run: str = typer.Option(..., "--run", "-r")) -> None:
    """Recompute metrics for an existing log."""
    out = write_metrics(run)
    console.print(f"metrics -> {out}")
    summary(run)


@app.command()
def summary(run: str = typer.Option(..., "--run", "-r")) -> None:
    """Print the headline numbers for a log."""
    m = compute_from_file(run)
    for sid, s in m["sessions"].items():
        console.print(f"\n[bold]session {sid}[/bold]  sequence={s['meta']['sequence_preset']}")
        t = Table("period", "state", "info", "trades", "mean price", "PI", "RE",
                  "E%", "TE%", "insider/uninf %")
        for row in s["paper"]["prices"]:
            p = str(row["period"])
            eff = s["paper"]["efficiency"].get(p) or {}
            ipr = s["paper"]["insider_profit_ratio"].get(p) or {}
            t.add_row(
                p, row["state"], row["info"], str(row["n_trades"]),
                f"{row['mean_price']:.1f}" if row["mean_price"] is not None else "-",
                str(row["pi_price"]), str(row["re_price"]),
                f"{eff.get('E_pct'):.1f}" if eff.get("E_pct") is not None else "-",
                f"{eff.get('TE_pct'):.1f}" if eff.get("TE_pct") is not None else "-",
                f"{ipr.get('ratio_pct'):.0f}" if ipr.get("ratio_pct") is not None else "-",
            )
        console.print(t)
        pc = s["paper"]["price_changes_toward_re"]
        for k in ("all", "separating"):
            v = pc[k]
            if v["n"]:
                console.print(f"  price changes toward RE ({k}): "
                              f"{v['toward_re']}/{v['n']} = {v['share_toward_re']:.1%}")
        tot = s["paper"]["totals"]
        if tot.get("insider_advantage_pct") is not None:
            console.print(f"  insider profit as % of uninformed (session): "
                          f"{tot['insider_advantage_pct']:.0f}%")
        if tot.get("cost_usd") is not None:
            console.print(f"  {tot['calls']} model calls, ${tot['cost_usd']}, "
                          f"{tot['wall_clock_s']}s")


if __name__ == "__main__":
    app()

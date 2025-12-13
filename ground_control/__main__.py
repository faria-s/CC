import sys
import time
import json
import argparse
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any


# ───────────────────────────────────────────────────────────────
# Helpers HTTP
# ───────────────────────────────────────────────────────────────

def fetch_json(url: str, timeout: float = 2.0) -> dict[str, Any] | None:
    """Faz GET a um URL e devolve JSON (dict) ou None se falhar."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
        return None


# ───────────────────────────────────────────────────────────────
# Estado local (para diff / offline / alertas)
# ───────────────────────────────────────────────────────────────

@dataclass
class RoverSnapshot:
    status: str | None = None
    mission_id: str | None = None 
    position: list[float] | None = None
    battery_level: float | None = None
    velocity: float | None = None
    last_seen_ts: float = 0.0
    missing_count: int = 0


@dataclass
class GCState:
    rovers: dict[str, RoverSnapshot] = field(default_factory=dict)
    missions_state: dict[str, dict[str, Any]] = field(default_factory=dict)


# ───────────────────────────────────────────────────────────────
# Formatação (dashboard)
# ───────────────────────────────────────────────────────────────

def clear_screen() -> None:
    # ANSI clear + home (funciona bem no terminal)
    print("\033[2J\033[H", end="")


def fmt_float(x: Any, nd: int = 2) -> str:
    try:
        return f"{float(x):.{nd}f}"
    except Exception:
        return "?"


def fmt_pos(pos: Any) -> str:
    if not isinstance(pos, list) or len(pos) < 2:
        return "?"
    if len(pos) == 2:
        return f"({fmt_float(pos[0])},{fmt_float(pos[1])})"
    return f"({fmt_float(pos[0])},{fmt_float(pos[1])},{fmt_float(pos[2])})"


def now_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


# ───────────────────────────────────────────────────────────────
# Leitura da API
# ───────────────────────────────────────────────────────────────

def get_missions(base_url: str) -> list[dict[str, Any]] | None:
    data = fetch_json(f"{base_url}/missions")
    if not data:
        return None
    missions = data.get("missions", [])
    return missions if isinstance(missions, list) else None


def get_rovers(base_url: str) -> list[dict[str, Any]] | None:
    data = fetch_json(f"{base_url}/rovers")
    if not data:
        return None
    rovers = data.get("rovers", [])
    return rovers if isinstance(rovers, list) else None


# ───────────────────────────────────────────────────────────────
# Diff (missões)
# ───────────────────────────────────────────────────────────────

def build_missions_state(missions_json: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    for m in missions_json:
        mid = m.get("mission_id")
        if not mid:
            continue
        state[str(mid)] = {
            "task": m.get("task"),
            "state": m.get("state"),
            "duration": m.get("duration"),
            "report_time": m.get("report_time"),
            "area": m.get("area"),
        }
    return state


def missions_changes(prev: dict[str, dict[str, Any]], new: dict[str, dict[str, Any]]) -> list[str]:
    out: list[str] = []

    # Novas / alteradas
    for mid, st in new.items():
        if mid not in prev:
            out.append(f"+ missão {mid} criada (estado={st.get('state')}, tarefa={st.get('task')})")
        else:
            if prev[mid] != st:
                # mostrar só campos que mudaram
                diffs = []
                for k in ("state", "task", "duration", "report_time", "area"):
                    if prev[mid].get(k) != st.get(k):
                        diffs.append(f"{k}: {prev[mid].get(k)} -> {st.get(k)}")
                out.append(f"~ missão {mid} atualizada | " + ", ".join(diffs))

    # Removidas
    for mid in prev.keys():
        if mid not in new:
            out.append(f"- missão {mid} removida")

    return out


# ───────────────────────────────────────────────────────────────
# Atualização de estado rovers + alertas
# ───────────────────────────────────────────────────────────────

def update_rovers_state(
    state: GCState,
    rovers_json: list[dict[str, Any]],
    offline_after: int,
) -> tuple[list[str], list[str]]:
    """
    Atualiza state.rovers.
    Devolve (changes, alerts).
    """
    ts = time.time()
    changes: list[str] = []
    alerts: list[str] = []

    seen: set[str] = set()

    for r in rovers_json:
        rid = r.get("rover_id")
        if not rid:
            continue
        rid = str(rid)
        seen.add(rid)

        last = r.get("last_telemetry") or {}
        status = r.get("status")
        pos = last.get("position")
        bat = last.get("battery_level")
        vel = last.get("velocity")

        snap = state.rovers.get(rid)
        if snap is None:
            snap = RoverSnapshot()
            state.rovers[rid] = snap
            changes.append(f"+ rover {rid} entrou (status={status})")

        # diffs “úteis”
        if snap.status != status:
            changes.append(f"~ rover {rid} status: {snap.status} -> {status}")
        if snap.battery_level is not None and bat is not None:
            try:
                if float(bat) < float(snap.battery_level):
                    # só registar queda se for “visível”
                    delta = float(snap.battery_level) - float(bat)
                    if delta >= 1.0:
                        changes.append(f"~ rover {rid} bateria: {fmt_float(snap.battery_level)} -> {fmt_float(bat)} (-{fmt_float(delta)})")
            except Exception:
                pass

        # aplicar valores
        snap.status = status
        snap.position = pos if isinstance(pos, list) else snap.position
        try:
            snap.battery_level = float(bat) if bat is not None else snap.battery_level
        except Exception:
            pass
        try:
            snap.velocity = float(vel) if vel is not None else snap.velocity
        except Exception:
            pass

        snap.last_seen_ts = ts
        snap.missing_count = 0

        # alertas
        if snap.battery_level is not None and snap.battery_level <= 20:
            alerts.append(f"! ALERTA bateria baixa: {rid} = {fmt_float(snap.battery_level)}%")

    # marcar ausentes (offline)
    for rid, snap in state.rovers.items():
        if rid not in seen:
            snap.missing_count += 1
            if snap.missing_count == offline_after:
                changes.append(f"- rover {rid} ficou OFFLINE (sem dados há {offline_after} ciclos)")
                alerts.append(f"! ALERTA rover offline: {rid}")

    return changes, alerts


# ───────────────────────────────────────────────────────────────
# Render dashboard
# ───────────────────────────────────────────────────────────────

def render_dashboard(
    base_url: str,
    state: GCState,
    last_errors: list[str],
    show_missions: bool,
) -> None:
    clear_screen()
    print(f"Ground Control @ {now_str()}")
    print(f"API: {base_url}")
    print()

    if last_errors:
        print("ERROS (mais recentes):")
        for e in last_errors[-3:]:
            print(f"  - {e}")
        print()

        # Rovers table
    print("ROVERS")
    print(f"{'rover_id':<10} {'status':<10} {'mission':<10} {'battery':>8} {'velocity':>9} {'position'}")
    print("-" * 70)

    if not state.rovers:
        print("(sem rovers ativos)")
    else:
        for rover_id, r in state.rovers.items():
            status = r.status or "?"
            mission = r.mission_id or "-"
            bat = r.battery_level
            vel = r.velocity
            pos = r.position

            bat_str = f"{bat:.2f}%" if isinstance(bat, (int, float)) else "-"
            vel_str = f"{vel:.2f}" if isinstance(vel, (int, float)) else "-"
            pos_str = str(tuple(pos)) if isinstance(pos, (list, tuple)) else "-"

            print(f"{rover_id:<10} {status:<10} {mission:<10} {bat_str:>8} {vel_str:>9} {pos_str}")


    print()


    # Missions summary (opcional)
    if show_missions:
        print("MISSÕES (lista)")
        print("mission_id   state         task")
        print("----------   ----------    ------------------------------")

        if not state.missions_state:
            print("(sem dados)\n")
        else:
            # ordena por número (M-001, M-002, ...)
            def mission_sort_key(mid: str):
                try:
                    return int(mid.split("-")[1])
                except Exception:
                    return mid

            for mid in sorted(state.missions_state.keys(), key=mission_sort_key):
                st = state.missions_state[mid]
                m_state = str(st.get("state", "?"))[:10].ljust(10)
                task = str(st.get("task", "?"))[:30]
                print(f"{mid.ljust(10)}   {m_state}    {task}")
            print()


# ───────────────────────────────────────────────────────────────
# Main
# ───────────────────────────────────────────────────────────────

def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser(prog="ground_control", add_help=True)
    p.add_argument("mothership_host", help="IP/hostname da Mothership (ex: 10.0.6.20)")
    p.add_argument("api_port", nargs="?", type=int, default=8000, help="Porta da API (default: 8000)")
    p.add_argument("--refresh", type=float, default=2.0, help="Intervalo de refresh (s)")
    p.add_argument("--dashboard", action="store_true", help="Mostra dashboard (limpa e redesenha)")
    p.add_argument("--show-missions", action="store_true", help="Mostra resumo de missões no dashboard")
    p.add_argument("--offline-after", type=int, default=3, help="Nº de ciclos sem dados para marcar OFFLINE")
    p.add_argument("--quiet", action="store_true", help="Não imprimir diffs (apenas dashboard)")
    args = p.parse_args(argv[1:])

    base_url = f"http://{args.mothership_host}:{args.api_port}"

    state = GCState()
    last_errors: list[str] = []

    # teste health
    h = fetch_json(f"{base_url}/health")
    if not h:
        print(f"[GroundControl] Aviso: não consegui contactar {base_url}/health")
    else:
        print(f"[GroundControl] Ligado à API: {base_url} | health={h}")

    try:
        while True:
            # missões
            missions = get_missions(base_url)
            if missions is None:
                last_errors.append("Falha ao obter /missions")
            else:
                new_m_state = build_missions_state(missions)
                if not args.quiet and new_m_state:
                    ch = missions_changes(state.missions_state, new_m_state)
                    if ch and not args.dashboard:
                        print("=== MISSÕES (alterações) ===")
                        for line in ch:
                            print(line)
                        print()
                state.missions_state = new_m_state

            # rovers
            rovers = get_rovers(base_url)
            if rovers is None:
                last_errors.append("Falha ao obter /rovers")
            else:
                changes, alerts = update_rovers_state(state, rovers, args.offline_after)

                if args.dashboard:
                    render_dashboard(base_url, state, last_errors, args.show_missions)
                    if alerts:
                        print("ALERTAS")
                        for a in alerts[-10:]:
                            print(" ", a)
                        print()
                else:
                    if not args.quiet and (changes or alerts):
                        print("=== ROVERS (alterações) ===")
                        for c in changes:
                            print(c)
                        if alerts:
                            print("--- ALERTAS ---")
                            for a in alerts:
                                print(a)
                        print()

            time.sleep(args.refresh)

    except KeyboardInterrupt:
        print("\nGround Control terminado.")


if __name__ == "__main__":
    main(sys.argv)

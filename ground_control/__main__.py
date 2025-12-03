import sys
import time
import json
import urllib.request
import urllib.error


REFRESH_INTERVAL = 3  # segundos

#python3.14 -m ground_control 10.0.2.15

def fetch_json(url: str):
    """Faz um GET ao URL e devolve JSON (ou None se falhar)"""
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
        print(f"[GroundControl] Erro ao pedir {url}: {e}")
        return None


# ---------- MISSÕES (diff) ----------

def build_missions_state(missions_json: list[dict]) -> dict:
    """
    Constrói um dicionário simples com o estado relevante de cada missão,
    indexado por mission_id, para podermos comparar com o anterior.
    """
    state = {}
    for m in missions_json:
        mid = m.get("mission_id")
        if mid is None:
            continue
        state[mid] = {
            "task": m.get("task"),
            "state": m.get("state"),
            "duration": m.get("duration"),
            "report_time": m.get("report_time"),
            "area": m.get("area"),
        }
    return state


def print_missions_diff(base_url: str, prev_state: dict) -> dict:
    """ Pede /missions, compara com o estado anterior e só imprime as alterações """
    url = f"{base_url}/missions"
    data = fetch_json(url)
    if not data:
        print("Não foi possível obter /missions.\n")
        return prev_state

    missions = data.get("missions", [])
    new_state = build_missions_state(missions)

    if not new_state and not prev_state:
        return new_state

    changes = []
    # Missões novas ou alteradas
    for mid, st in new_state.items():
        if mid not in prev_state or prev_state[mid] != st:
            changes.append((mid, st))

    # Missões que desapareceram
    removed = [mid for mid in prev_state.keys() if mid not in new_state]

    if not changes and not removed:
        # Nada mudou → não imprimir
        return new_state

    print("=== MISSÕES (alterações) ===")
    for mid, st in changes:
        print(
            f"- {mid} | tarefa={st['task']} | estado={st['state']} | "
            f"dur={st['duration']}s | report={st['report_time']}s | area={st['area']}"
        )
    for mid in removed:
        print(f"- {mid} foi removida")

    print()
    return new_state


# ---------- ROVERS (diff) ----------

def build_rover_state(rovers_json: list[dict]) -> dict:
    """
    Constrói um dicionário simples com o estado relevante de cada rover,
    para podermos comparar com o anterior.
    """
    state = {}
    for r in rovers_json:
        rover_id = r.get("rover_id")
        if rover_id is None:
            continue
        status = r.get("status")
        last = r.get("last_telemetry", {}) or {}

        state[rover_id] = {
            "status": status,
            "position": last.get("position"),
            "battery_level": last.get("battery_level"),
            "velocity": last.get("velocity"),
        }
    return state


def print_rovers_diff(base_url: str, prev_state: dict) -> dict:
    """ Pede /rovers, compara com o estado anterior e só imprime as alterações """
    url = f"{base_url}/rovers"
    data = fetch_json(url)
    if not data:
        print("Não foi possível obter /rovers.\n")
        return prev_state

    rovers = data.get("rovers", [])
    new_state = build_rover_state(rovers)

    if not new_state and not prev_state:
        return new_state

    changes = []
    for rover_id, st in new_state.items():
        if rover_id not in prev_state or prev_state[rover_id] != st:
            changes.append((rover_id, st))

    removed = [rid for rid in prev_state.keys() if rid not in new_state]

    if not changes and not removed:
        return new_state

    print("=== ROVERS / TELEMETRIA (alterações) ===")
    for rover_id, st in changes:
        pos = st["position"]
        bat = st["battery_level"]
        vel = st["velocity"]
        status = st["status"]
        print(
            f"- {rover_id} | estado={status} | "
            f"pos={pos} | bat={bat}% | vel={vel} m/s"
        )

    for rover_id in removed:
        print(f"- {rover_id} deixou de estar ativo")

    print()
    return new_state


# ---------- MAIN ----------

def main(argv: list[str]) -> None:
    if len(argv) != 2 and len(argv) != 3:
        print("Usage: python -m ground_control <mothership_host> [api_port]")
        sys.exit(1)

    host = argv[1]
    port = int(argv[2]) if len(argv) == 3 else 8000

    base_url = f"http://{host}:{port}"

    print(f"Ground Control ligado à API em {base_url}")
    print("CTRL+C para sair.\n")

    # Teste rápido de /health
    health = fetch_json(f"{base_url}/health")
    if health:
        print(f"API health: {health}\n")
    else:
        print("Aviso: não foi possível contactar /health.\n")

    prev_missions_state: dict = {}
    prev_rovers_state: dict = {}

    try:
        while True:
            prev_missions_state = print_missions_diff(base_url, prev_missions_state)
            prev_rovers_state = print_rovers_diff(base_url, prev_rovers_state)
            time.sleep(REFRESH_INTERVAL)
    except KeyboardInterrupt:
        print("\nGround Control terminado.")


if __name__ == "__main__":
    main(sys.argv)

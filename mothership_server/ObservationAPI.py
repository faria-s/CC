from flask import Flask, jsonify
from typing import Any

from lib.logging import log
from lib.structs.Mission import MissionState
from lib.structs.Telemetry import Telemetry, OperationalStatus


#curl http://10.0.2.15:8000/missions
#curl http://10.0.2.15:8000/telemetry/latest
#curl http://10.0.2.15:8000/health

#python -m ground_control 10.0.6.20 8000 --dashboard --show-missions


# Tipos esperados:
# - database: instância de mothership-server/Database.Database
# - telemetry_server: instância de lib.TelemetryStream.TelemetryStreamServer


def telemetry_to_dict(t: Telemetry) -> dict[str, Any]:
    """Converte um objeto Telemetry num dicionário JSON-friendly."""
    return {
        "rover_id": t.rover_id,
        "mission_id": t.mission_id,
        "position": list(t.position),
        "battery_level": t.battery_level,
        "velocity": t.velocity,
        "operational_status": t.operational_status.name,
    }


def create_app(database, telemetry_server) -> Flask:
    app = Flask(__name__)

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    @app.route("/missions", methods=["GET"])
    def get_missions():
        """
        Devolve a lista de missões (ativas e concluídas).
        Lido da base de dados.
        """
        try:
            rows = database.fetch_all_missions()
            missions = []

            for mission_id, area, task, duration, report_time, state_int in rows:
                # area já vem como lista de coords do Database
                try:
                    state = MissionState(state_int).name
                except ValueError:
                    state = "UNKNOWN"

                missions.append(
                    {
                        "mission_id": mission_id,
                        "area": area,  # [[x1, y1], [x2, y2]]
                        "task": task,
                        "duration": duration,
                        "report_time": report_time,
                        "state": state,
                    }
                )

            return jsonify({"missions": missions}), 200

        except Exception as e:
            log(f"[API] Error fetching missions: {e}", "Error")
            return jsonify({"error": "failed to fetch missions"}), 500

    @app.route("/telemetry/latest", methods=["GET"])
    def get_latest_telemetry():
        """
        Devolve a última telemetria de cada rover.
        Lida do TelemetryStreamServer.telemetry_data.
        """
        try:
            with telemetry_server.lock:
                data = {
                    rover_id: telemetry_to_dict(t)
                    for rover_id, t in telemetry_server.telemetry_data.items()
                }

            return jsonify({"telemetry": data}), 200

        except Exception as e:
            log(f"[API] Error fetching telemetry: {e}", "Error")
            return jsonify({"error": "failed to fetch telemetry"}), 500

    @app.route("/rovers", methods=["GET"])
    def get_rovers():
        """
        Devolve a lista de rovers ativos e o seu estado atual.

        Aqui consideramos 'ativos' os rovers que já enviaram telemetria.
        Estado = operational_status da Telemetry.
        """
        try:
            rovers = []

            with telemetry_server.lock:
                for rover_id, t in telemetry_server.telemetry_data.items():
                    rovers.append(
                        {
                            "rover_id": rover_id,
                            "status": t.operational_status.name,
                            "last_telemetry": telemetry_to_dict(t),
                        }
                    )

            return jsonify({"rovers": rovers}), 200

        except Exception as e:
            log(f"[API] Error fetching rovers: {e}", "Error")
            return jsonify({"error": "failed to fetch rovers"}), 500

    return app


def run_api(database, telemetry_server, host: str = "0.0.0.0", port: int = 8000):
    """
    Arranca a API Flask num thread separado (se for chamado a partir de outro módulo).
    """
    app = create_app(database, telemetry_server)
    log(f"[API] Starting Observation API on {host}:{port}", "Info")
    app.run(host=host, port=port, debug=False, use_reloader=False)

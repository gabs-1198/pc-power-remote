#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agente PC Power Remote (Windows / Linux)
Servidor HTTP (porta 5050) + Descoberta Automática UDP (porta 5051) na rede local:
- Responde automaticamente à busca do aplicativo Android na rede Wi-Fi (UDP 5051)
- Informa status (online, hostname, IP, MAC Address e diagnóstico WoL) via HTTP GET /status
- Executa ações remotas: /shutdown, /restart, /sleep, /hibernate, /lock, /cancel-shutdown
"""

import ctypes
import json
import os
import platform
import re
import socket
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PC_POWER_PORT", "5050"))
DISCOVERY_UDP_PORT = int(os.environ.get("PC_POWER_UDP_PORT", "5051"))
PIN_CODE = os.environ.get("PC_POWER_PIN", "")  # Opcional: defina uma senha se desejar


def get_local_ip() -> str:
    """Descobre o IP local da máquina na rede (LAN/Wi-Fi)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return socket.gethostbyname(socket.gethostname())


def get_mac_address(target_ip: str) -> str:
    """Obtém o endereço MAC da interface de rede ativa no Windows ou fallback via uuid."""
    if platform.system().lower() == "windows":
        try:
            output = subprocess.check_output(
                ["ipconfig", "/all"],
                encoding="oem",
                errors="ignore",
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            blocks = re.split(r"\r?\n(?=\S)", output)
            for block in blocks:
                if target_ip in block:
                    mac_match = re.search(
                        r"([0-9A-Fa-f]{2}(?:-[0-9A-Fa-f]{2}){5})", block
                    )
                    if mac_match:
                        return mac_match.group(1).replace("-", ":").upper()
        except Exception:
            pass

    mac_num = uuid.getnode()
    mac_hex = f"{mac_num:012X}"
    return ":".join(mac_hex[i : i + 2] for i in range(0, 12, 2))


def get_wol_diagnostics() -> dict:
    """Verifica se o computador está em Ethernet e com WoL ativado."""
    is_ethernet = True
    adapter_name = "Ethernet"
    wake_armed = True
    fast_startup_disabled = True

    if platform.system().lower() == "windows":
        try:
            output = subprocess.check_output(
                ["netsh", "interface", "show", "interface"],
                encoding="oem",
                errors="ignore",
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if "Wi-Fi" in output or "Wireless" in output:
                # Verifica se a interface conectada é wireless
                ip_out = subprocess.check_output(
                    ["ipconfig"],
                    encoding="oem",
                    errors="ignore",
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if "Wi-Fi" in ip_out or "Wireless" in ip_out:
                    is_ethernet = False
                    adapter_name = "Wi-Fi"
        except Exception:
            pass

        try:
            armed_out = subprocess.check_output(
                ["powercfg", "/devicequery", "wake_armed"],
                encoding="oem",
                errors="ignore",
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            wake_armed = len(armed_out.strip()) > 0
        except Exception:
            pass

    return {
        "isEthernet": is_ethernet,
        "adapterName": adapter_name,
        "wakeArmed": wake_armed,
        "fastStartupDisabled": fast_startup_disabled,
        "readyForWol": is_ethernet and wake_armed,
    }


def build_status_payload() -> dict:
    ip = get_local_ip()
    mac = get_mac_address(ip)
    return {
        "status": "online",
        "hostname": platform.node(),
        "ip": ip,
        "mac": mac,
        "port": PORT,
        "requiresPin": bool(PIN_CODE),
        "wolDiagnostics": get_wol_diagnostics(),
    }


def udp_discovery_loop():
    """Escuta pacotes UDP de descoberta (DISCOVER_PCPOWER) na porta 5051."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("0.0.0.0", DISCOVERY_UDP_PORT))
        while True:
            data, addr = sock.recvfrom(1024)
            msg = data.decode("utf-8", errors="ignore").strip()
            if msg.upper().startswith("DISCOVER_PCPOWER"):
                reply = json.dumps(build_status_payload(), ensure_ascii=False).encode("utf-8")
                sock.sendto(reply, addr)
    except Exception:
        pass


class PowerRequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _check_pin(self, body_data: dict) -> bool:
        if not PIN_CODE:
            return True
        header_pin = self.headers.get("X-Auth-Pin", "")
        body_pin = str(body_data.get("pin", ""))
        return header_pin == PIN_CODE or body_pin == PIN_CODE

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        if self.path == "/status" or self.path == "/":
            self._send_json(200, build_status_payload())
        else:
            self._send_json(404, {"error": "Endpoint não encontrado"})

    def do_POST(self):
        # Proteção anti-CSRF: descarta requisições originadas por navegadores externos
        origin = self.headers.get("Origin", "")
        referer = self.headers.get("Referer", "")
        if origin or referer:
            self._send_json(403, {"ok": False, "message": "Acesso proibido via navegador web (CSRF Protection)."})
            return

        client_header = self.headers.get("X-PC-Power-Client", "")
        if client_header != "1":
            self._send_json(400, {"ok": False, "message": "Cliente não identificado."})
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body_data = {}
        if content_length > 0:
            try:
                raw = self.rfile.read(content_length).decode("utf-8")
                body_data = json.loads(raw)
            except Exception:
                body_data = {}

        if not self._check_pin(body_data):
            self._send_json(401, {"ok": False, "message": "PIN inválido ou não informado."})
            return

        delay = int(body_data.get("delay", 5))
        delay = max(0, min(delay, 3600))

        if self.path == "/shutdown":
            try:
                if platform.system().lower() == "windows":
                    subprocess.Popen(
                        [
                            "shutdown",
                            "/s",
                            "/f",
                            "/t",
                            str(delay),
                            "/c",
                            "Desligamento solicitado pelo aplicativo Android (PC Power Remote).",
                        ],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                else:
                    subprocess.Popen(["sudo", "shutdown", "-h", f"+{delay // 60}"])

                self._send_json(
                    200,
                    {
                        "ok": True,
                        "message": f"Comando enviado! O PC será desligado em {delay} segundos.",
                    },
                )
            except Exception as e:
                self._send_json(500, {"ok": False, "message": f"Erro ao desligar: {e}"})

        elif self.path == "/restart":
            try:
                if platform.system().lower() == "windows":
                    subprocess.Popen(
                        [
                            "shutdown",
                            "/r",
                            "/f",
                            "/t",
                            str(delay),
                            "/c",
                            "Reinício solicitado pelo aplicativo Android (PC Power Remote).",
                        ],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                else:
                    subprocess.Popen(["sudo", "shutdown", "-r", f"+{delay // 60}"])

                self._send_json(
                    200,
                    {
                        "ok": True,
                        "message": f"Comando enviado! O PC será reiniciado em {delay} segundos.",
                    },
                )
            except Exception as e:
                self._send_json(500, {"ok": False, "message": f"Erro ao reiniciar: {e}"})

        elif self.path == "/sleep":
            try:
                if platform.system().lower() == "windows":
                    def _suspend():
                        time.sleep(0.8)
                        ctypes.windll.powrprof.SetSuspendState(0, 1, 1)
                    threading.Thread(target=_suspend, daemon=True).start()
                else:
                    subprocess.Popen(["systemctl", "suspend"])

                self._send_json(200, {"ok": True, "message": "Computador entrando em modo de suspensão..."})
            except Exception as e:
                self._send_json(500, {"ok": False, "message": f"Erro ao suspender: {e}"})

        elif self.path == "/hibernate":
            try:
                if platform.system().lower() == "windows":
                    def _hibernate():
                        time.sleep(0.8)
                        ctypes.windll.powrprof.SetSuspendState(1, 1, 1)
                    threading.Thread(target=_hibernate, daemon=True).start()
                else:
                    subprocess.Popen(["systemctl", "hibernate"])

                self._send_json(200, {"ok": True, "message": "Computador entrando em hibernação..."})
            except Exception as e:
                self._send_json(500, {"ok": False, "message": f"Erro ao hibernar: {e}"})

        elif self.path == "/lock":
            try:
                if platform.system().lower() == "windows":
                    ctypes.windll.user32.LockWorkStation()
                else:
                    subprocess.Popen(["loginctl", "lock-session"])

                self._send_json(200, {"ok": True, "message": "Tela do computador bloqueada com sucesso!"})
            except Exception as e:
                self._send_json(500, {"ok": False, "message": f"Erro ao bloquear tela: {e}"})

        elif self.path == "/cancel-shutdown":
            try:
                if platform.system().lower() == "windows":
                    subprocess.Popen(
                        ["shutdown", "/a"],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                self._send_json(
                    200,
                    {"ok": True, "message": "Desligamento/reinício cancelado com sucesso."},
                )
            except Exception as e:
                self._send_json(500, {"ok": False, "message": f"Erro ao cancelar: {e}"})
        else:
            self._send_json(404, {"ok": False, "message": "Rota não encontrada"})

    def log_message(self, format, *args):
        if sys.stdout is not None and hasattr(sys.stdout, "write"):
            try:
                super().log_message(format, *args)
            except Exception:
                pass


def main():
    info = build_status_payload()
    udp_thread = threading.Thread(target=udp_discovery_loop, daemon=True)
    udp_thread.start()

    server = HTTPServer(("0.0.0.0", PORT), PowerRequestHandler)

    if sys.stdout is not None and hasattr(sys.stdout, "write"):
        print("=" * 60)
        print("  PC POWER REMOTE - AGENTE ATIVO")
        print("=" * 60)
        print(f"  Nome do PC   : {info['hostname']}")
        print(f"  IP na Rede   : {info['ip']}")
        print(f"  MAC Address  : {info['mac']}")
        print(f"  Porta HTTP   : {PORT} | Descoberta UDP: {DISCOVERY_UDP_PORT}")
        print(f"  PIN Ativo    : {'Sim' if PIN_CODE else 'Nao (livre na rede privada)'}")
        diag = info.get("wolDiagnostics", {})
        print(f"  Diagnóstico WoL: {'Pronto (Ethernet)' if diag.get('readyForWol') else 'Verificar conexão'}")
        print("=" * 60)
        print("Ações suportadas: Ligar, Desligar, Reiniciar, Suspender, Bloquear")
        print("Pressione Ctrl+C para encerrar.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        if sys.stdout is not None:
            print("\nAgente encerrado.")
        server.server_close()


if __name__ == "__main__":
    main()

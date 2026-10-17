"""
Agentic Live Bridge listener for debim-ingetrazo.
Provides a local JSON-RPC / HTTP server on localhost:8482 for external AI agents
to stream and inject raw .debim content into IngeTrazo.
"""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Dict, Optional, Tuple, Union

from debim_ingetrazo.builder import BuildingModel, build_geometry
from debim_ingetrazo.parser import parse_debim_str

logger = logging.getLogger("debim_ingetrazo.agent_bridge")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8482


class AgentBridgeRequestHandler(BaseHTTPRequestHandler):
    """
    HTTP Handler supporting JSON-RPC 2.0 and direct HTTP POST for streaming .debim manifests.
    """

    server: "AgentBridgeServer"  # Type hint for custom server

    def log_message(self, format_str: str, *args: Any) -> None:
        # Suppress standard http server log spam in console unless needed
        logger.debug(format_str, *args)

    def _send_json_response(self, data: Dict[str, Any], code: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        """Endpoint status probe."""
        status_info = {
            "status": "online",
            "service": "debim-ingetrazo Agent Bridge",
            "host": self.server.host,
            "port": self.server.port,
            "received_count": self.server.received_count,
        }
        self._send_json_response(status_info)

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")

        # Try parsing as JSON-RPC or JSON object
        is_json = False
        data: Dict[str, Any] = {}
        try:
            data = json.loads(post_data)
            if isinstance(data, dict):
                is_json = True
        except Exception:
            is_json = False

        if is_json and "jsonrpc" in data:
            self._handle_json_rpc(data)
        elif is_json:
            # Simple JSON payload {"content": "..."} or {"debim": "..."}
            debim_str = data.get("content") or data.get("debim") or data.get("manifest")
            if not debim_str and isinstance(data, dict):
                # Fallback: maybe raw dict is YAML serialized or json manifest
                debim_str = post_data
            self._process_debim_string(str(debim_str), req_id=None, is_rpc=False)
        else:
            # Raw string body (.debim format)
            self._process_debim_string(post_data, req_id=None, is_rpc=False)

    def _handle_json_rpc(self, rpc_req: Dict[str, Any]) -> None:
        req_id = rpc_req.get("id")
        method = rpc_req.get("method", "")
        params = rpc_req.get("params", {})

        if not isinstance(params, dict):
            params = {"content": str(params)}

        if method in ("render_manifest", "update_debim", "inject_debim", "push_debim"):
            content = params.get("content") or params.get("debim") or params.get("manifest") or ""
            if not content:
                err_resp = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32602, "message": "Missing 'content' parameter in params."},
                    "id": req_id,
                }
                self._send_json_response(err_resp, code=400)
                return

            self._process_debim_string(str(content), req_id=req_id, is_rpc=True)

        elif method == "get_status":
            resp = {
                "jsonrpc": "2.0",
                "result": {
                    "status": "online",
                    "host": self.server.host,
                    "port": self.server.port,
                    "received_count": self.server.received_count,
                },
                "id": req_id,
            }
            self._send_json_response(resp)

        else:
            err_resp = {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method '{method}' not found."},
                "id": req_id,
            }
            self._send_json_response(err_resp, code=404)

    def _process_debim_string(self, content_str: str, req_id: Optional[Any], is_rpc: bool) -> None:
        try:
            manifest_dict = parse_debim_str(content_str)
            building_model = build_geometry(manifest_dict)

            self.server.received_count += 1
            if self.server.get_callback():
                self.server.get_callback()(content_str, manifest_dict, building_model)

            res_payload = {
                "status": "success",
                "message": ".debim manifest parsed and injected successfully.",
                "model_name": building_model.name,
                "storeys_count": len(building_model.storeys),
                "model_dict": building_model.to_dict(),
            }

            if is_rpc:
                response = {"jsonrpc": "2.0", "result": res_payload, "id": req_id}
            else:
                response = res_payload

            self._send_json_response(response, code=200)

        except Exception as e:
            logger.exception("Error processing .debim payload: %s", e)
            err_payload = {
                "status": "error",
                "message": f"Failed to parse/render .debim content: {str(e)}",
            }
            if is_rpc:
                response = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": str(e)},
                    "id": req_id,
                }
            else:
                response = err_payload

            self._send_json_response(response, code=400)


class AgentBridgeServer(HTTPServer):
    """Custom HTTPServer maintaining server state and callback registration."""

    allow_reuse_address = True

    def __init__(
        self,
        server_address: Tuple[str, int],
        RequestHandlerClass: Any,
        parent_bridge: Optional["AgentBridge"] = None,
    ):
        super().__init__(server_address, RequestHandlerClass)
        self.host = server_address[0]
        self.port = server_address[1]
        self.parent_bridge = parent_bridge
        self.received_count = 0

    def get_callback(self) -> Optional[Callable[[str, Dict[str, Any], BuildingModel], Any]]:
        if self.parent_bridge:
            return self.parent_bridge.on_debim_received
        return None


class AgentBridge:
    """
    Background HTTP / JSON-RPC Agent Bridge server manager.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        on_debim_received: Optional[Callable[[str, Dict[str, Any], BuildingModel], Any]] = None,
    ):
        self.host = host
        self.port = port
        self.on_debim_received = on_debim_received
        self._server: Optional[AgentBridgeServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running and self._server is not None

    def start(self) -> None:
        """Starts the Agent Bridge server in a background thread."""
        if self._running:
            return

        self._server = AgentBridgeServer(
            (self.host, self.port),
            AgentBridgeRequestHandler,
            parent_bridge=self,
        )
        self._running = True
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True, name="DebimAgentBridgeThread"
        )
        self._thread.start()
        logger.info("Agent Bridge server started at http://%s:%d", self.host, self.port)

    def stop(self) -> None:
        """Stops the Agent Bridge server."""
        if not self._running or self._server is None:
            return

        self._server.shutdown()
        self._server.server_close()
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._server = None
        self._thread = None
        logger.info("Agent Bridge server stopped.")

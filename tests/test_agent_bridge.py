import json
import time
import urllib.request
import urllib.error
import pytest

from debim_ingetrazo.agent_bridge import AgentBridge, DEFAULT_PORT


TEST_BRIDGE_PORT = 18482


@pytest.fixture
def agent_bridge_server():
    # Use dedicated test port so tests don't conflict with a running IngeTrazo instance on 8482
    bridge = AgentBridge(host="127.0.0.1", port=TEST_BRIDGE_PORT)
    bridge.start()
    time.sleep(0.1)
    yield bridge
    bridge.stop()


def test_agent_bridge_get_status(agent_bridge_server):
    assert agent_bridge_server.is_running
    url = f"http://127.0.0.1:{agent_bridge_server.port}/"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "online"
        assert data["service"] == "debim-ingetrazo Agent Bridge"


def test_agent_bridge_post_raw_debim(agent_bridge_server):
    received_models = []

    def on_received(content, manifest, model):
        received_models.append(model)

    agent_bridge_server.on_debim_received = on_received

    debim_text = """
project:
  name: Test Bridge House
building:
  storeys:
    - id: L1
      name: Level 1
"""
    url = f"http://127.0.0.1:{agent_bridge_server.port}/"
    req = urllib.request.Request(
        url, data=debim_text.encode("utf-8"), headers={"Content-Type": "text/plain"}, method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        res = json.loads(resp.read().decode("utf-8"))
        assert res["status"] == "success"
        assert res["model_name"] == "Test Bridge House"

    assert len(received_models) == 1
    assert received_models[0].name == "Test Bridge House"


def test_agent_bridge_json_rpc_render_manifest(agent_bridge_server):
    received_models = []
    agent_bridge_server.on_debim_received = lambda c, m, b: received_models.append(b)

    rpc_payload = {
        "jsonrpc": "2.0",
        "method": "render_manifest",
        "params": {
            "content": "project:\n  name: RPC Building\n"
        },
        "id": 42
    }

    url = f"http://127.0.0.1:{agent_bridge_server.port}/"
    req = urllib.request.Request(
        url, data=json.dumps(rpc_payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        res = json.loads(resp.read().decode("utf-8"))
        assert res["jsonrpc"] == "2.0"
        assert res["id"] == 42
        assert res["result"]["status"] == "success"
        assert res["result"]["model_name"] == "RPC Building"

    assert len(received_models) == 1
    assert received_models[0].name == "RPC Building"


def test_agent_bridge_json_rpc_get_status(agent_bridge_server):
    rpc_payload = {
        "jsonrpc": "2.0",
        "method": "get_status",
        "params": {},
        "id": 101
    }

    url = f"http://127.0.0.1:{agent_bridge_server.port}/"
    req = urllib.request.Request(
        url, data=json.dumps(rpc_payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        res = json.loads(resp.read().decode("utf-8"))
        assert res["id"] == 101
        assert res["result"]["status"] == "online"

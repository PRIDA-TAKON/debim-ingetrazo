import urllib.request
import json

manifest = """
project:
  name: "Villa with Spread Footings"
  units: "m"
storeys:
  - id: "ST_01"
    name: "Ground Floor"
    elevation: 0.0
    height: 3.2
    slabs:
      - id: "SLAB_GF"
        name: "Ground Slab"
        thickness: 0.25
        elevation: 0.0
        boundary: [[0, 0], [10, 0], [10, 8], [0, 8]]
      # ฐานรากคอนกรีต ฐานแผ่ 1x1x0.3 m ใต้เสาทั้ง 4 มุม (elevation -0.3 ถึง 0.0)
      - id: "F1_C1"
        name: "Spread Footing F1"
        tag: "S-FOOTING"
        thickness: 0.3
        elevation: -0.3
        boundary: [[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]]
      - id: "F2_C2"
        name: "Spread Footing F2"
        tag: "S-FOOTING"
        thickness: 0.3
        elevation: -0.3
        boundary: [[9.5, -0.5], [10.5, -0.5], [10.5, 0.5], [9.5, 0.5]]
      - id: "F3_C3"
        name: "Spread Footing F3"
        tag: "S-FOOTING"
        thickness: 0.3
        elevation: -0.3
        boundary: [[9.5, 7.5], [10.5, 7.5], [10.5, 8.5], [9.5, 8.5]]
      - id: "F4_C4"
        name: "Spread Footing F4"
        tag: "S-FOOTING"
        thickness: 0.3
        elevation: -0.3
        boundary: [[-0.5, 7.5], [0.5, 7.5], [0.5, 8.5], [-0.5, 8.5]]
    columns:
      - id: "C1"
        position: [0, 0]
        section: [0.4, 0.4]
        height: 3.2
        elevation: 0.0
      - id: "C2"
        position: [10, 0]
        section: [0.4, 0.4]
        height: 3.2
        elevation: 0.0
      - id: "C3"
        position: [10, 8]
        section: [0.4, 0.4]
        height: 3.2
        elevation: 0.0
      - id: "C4"
        position: [0, 8]
        section: [0.4, 0.4]
        height: 3.2
        elevation: 0.0
    walls:
      - id: "W1"
        start: [0, 0]
        end: [10, 0]
        thickness: 0.2
        height: 3.2
      - id: "W2"
        start: [10, 0]
        end: [10, 8]
        thickness: 0.2
        height: 3.2
      - id: "W3"
        start: [10, 8]
        end: [0, 8]
        thickness: 0.2
        height: 3.2
      - id: "W4"
        start: [0, 8]
        end: [0, 0]
        thickness: 0.2
        height: 3.2
"""

req = urllib.request.Request(
    "http://127.0.0.1:8482",
    data=manifest.encode("utf-8"),
    headers={"Content-Type": "text/plain; charset=utf-8"},
    method="POST",
)

with urllib.request.urlopen(req, timeout=5) as resp:
    print("HTTP Code:", resp.status)
    print("Response:", resp.read().decode("utf-8"))

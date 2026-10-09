# ⚡ Aura Atlas: Autonomous Multi-Agent Warehouse Swarm Coordinator

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Aura Atlas** is a high-performance, real-time multi-agent autonomous mobile robot (AMR) swarm simulation and coordinator designed for smart warehouse fulfillment. It integrates global path planning, decentralized conflict resolution, auction-based task dispatch, station inventory logistics, and a rich dark-mode browser dashboard.

---

## 📌 Core Architecture & Features

### 1. 🤖 Decentralized Conflict Resolution: PIBT
- Implements **Priority Inheritance with Backtracking (PIBT)** (Okumura et al., 2022).
- When a higher-priority robot is obstructed by another agent along its trajectory, priority is dynamically inherited, pushing the occupying agent out of the bottleneck or into an adjacent free cell.
- Cycle detection guards prevent infinite recursion, and stationary (idle/failed) agents are preserved as immovable obstacles.
- Emits real-time collaborative messages (`yield`, `detour`) to the simulation event bus.

### 2. 🗺️ Global Guidance: Space-Time A* & Reservation Table
- Space-time 4D search $(x, y, t)$ guides robots toward pick and drop targets while avoiding vertex $(x, y, t)$ and swap conflicts $(x_1 \to x_2 \land x_2 \to x_1 \text{ at } t \to t+1)$.
- Dynamic planning horizon adapts to ongoing simulation ticks without arbitrary horizon cutoff.

### 3. 🔮 Predictive Conflict Analysis
- A dedicated lookahead conflict engine inspects planned paths up to 8 ticks ahead.
- Predicts vertex and swap conflicts before they occur, scoring each predicted collision by urgency and confidence.

### 4. 📦 Fair Auction Task Dispatch & Capacity Logistics
- **Auction Engine**: Only unassigned (`idle`) robots bid on pending orders. Noise-augmented bidding ensures balanced order distribution across the fleet rather than concentrating workload on the nearest robot.
- **Station Inventory Management**: Pick stations hold stock and decrement upon pickup; drop stations receive items. Low pick stations are automatically restocked.
- **Station Prioritization**: User-configurable priorities (1–3) dynamically skew auction generation toward high-throughput zones.
- **Multi-Package Carrying**: Robots support carrying capacity ($\times 1, \times 2, \times 3$ packages per trip).

### 5. 🏗️ Standard Benchmark Map Support (MovingAI)
- Supports synthetic and standard **MovingAI MAPF benchmark maps** (e.g., `warehouse-10-20-10-2-1`, `maze-32-32-2`, `random-32-32-10`).
- Automated download engine extracts compressed `.map.zip` benchmarks directly.
- `auto_stations()` heuristic scans warehouse layouts to place evenly spaced pick and drop stations.

### 6. 🖥️ Interactive Dashboard & Visualizer
- **HTML5 Canvas Visualizer**: Adaptive scaling from small layouts up to large 161×63 maps.
- **Real-Time Overlays**:
  - 🌡 **Heatmap**: Visualizes traffic density and aisle bottlenecks.
  - 🎯 **Directed Routes**: Displays dashed trajectories (pickup phase) and solid vectors with pulsing destination rings (dropoff phase).
- **Control Panels**:
  - **Map & Fleet Configuration**: Robot count (1–50), capacity selector, map switcher.
  - **Task Assignments**: Real-time phase tracking (`PICKING`, `DROPPING`, `IDLE`), carried packages, and progress indicators.
  - **Station Inventory**: Live inventory capacity bars and click-to-set priority toggles.
  - **Conflict Predictions**: Live collision warning cards with confidence bars.
  - **Hive Mind Feed**: Color-coded log of agent negotiations (`yield`, `detour`, `pickup`, `delivery`, `fail`).
  - **Performance Metrics**: Ticks, throughput per 100 ticks, average delivery duration, and fleet efficiency.

---

## 📂 Project Structure

```
Aura-Atlas/
├── requirements.txt         # Python dependencies (FastAPI, Uvicorn, NumPy)
├── main.py                  # FastAPI server, WebSocket hub & REST endpoints
├── sim/
│   ├── __init__.py          # Package initialization
│   ├── grid.py              # Warehouse grid generator & MovingAI map parser
│   ├── reservation.py       # Space-time reservation table (vertex + swap conflicts)
│   ├── astar.py             # Space-time A* pathfinding algorithm
│   ├── pibt.py              # Priority Inheritance with Backtracking (PIBT) engine
│   ├── station.py           # Pick/drop station model & inventory tracker
│   ├── predictor.py         # Predictive lookahead conflict analyzer
│   ├── robot.py             # Robot agent state machine, bidding, & lifecycle
│   └── simulator.py         # Multi-agent coordinator & event loop
├── maps/                    # MovingAI benchmark map files (.map)
│   ├── warehouse-10-20-10-2-1.map
│   └── maze-32-32-2.map
├── static/
│   └── index.html           # Dark-mode dashboard, HTML5 canvas, & real-time UI
├── .gitignore
└── README.md
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.9 or higher
- Git

### 2. Installation & Setup

Clone the repository and set up a virtual environment:

```bash
git clone https://github.com/subramanyam-11/Aura-Atlas.git
cd Aura-Atlas

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

### 3. Running the Simulator

Launch the FastAPI application with Uvicorn:

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Open your browser and navigate to:
```
http://localhost:8000
```

---

## 🎮 How to Use the Dashboard

1. **Start the Fleet**: Click **▶ Start** in the sidebar. Robots will spawn, receive auction-allocated tasks, plan space-time paths, and begin executing pick-and-drop operations.
2. **Inject Dynamic Obstacles**: Click **🚧 Block Mode**, then click any open grid cell to place an obstacle in real time. Passing robots will adaptively replan around it.
3. **Trigger Robot Failures**: Click any robot chip in the sidebar (e.g., `R0`, `R1`). The robot will halt with an alert cross, release its reservation, and its unfulfilled task will be re-auctioned to an idle peer.
4. **Change Station Priorities**: In the **Stations** panel, toggle priority buttons (`1`, `2`, or `3`) on any pick station to increase order generation weight.
5. **Toggle Overlays**:
   - Click **🌡 Heatmap** to inspect intersection traffic load.
   - Click **🎯 Routes** to view vector headings toward current goals.
6. **Load Benchmark Maps**:
   - Choose a map from the dropdown (e.g., `warehouse-10-20-10-2-1` or `maze-32-32-2`).
   - Select fleet size (e.g., `20` robots).
   - Click **⬇ Download** (if not locally present), then **Load Map**.

---

## 📡 REST API & WebSocket Protocol

### Control Endpoints
- `POST /control/start`: Starts or resumes the simulation loop.
- `POST /control/pause`: Pauses simulation execution.
- `POST /control/reset`: Resets grid, robots, and stations to initial state.

### Event Endpoints
- `POST /event/order`: Dispatches an order `{"priority": int, "qty": int}`.
- `POST /event/block`: Blocks a coordinate `{"x": int, "y": int}`.
- `POST /event/fail/{rid}`: Simulates failure for robot ID `{rid}`.
- `POST /station/{sid}/priority`: Updates priority `{"priority": int}` for station `{sid}`.

### Map Endpoints
- `GET /map/available`: Lists local and built-in benchmark maps.
- `POST /map/download/{name}`: Fetches and extracts a MovingAI `.map` file.
- `POST /map/switch`: Hot-swaps the current map and robot fleet `{"map_name": str, "num_robots": int, "robot_capacity": int}`.

### Real-Time WebSocket
- `ws://localhost:8000/ws`: Streams JSON frames containing tick status, robot positions, paths, station inventories, predicted conflicts, Hive Mind events, and metrics.

---

## 🔬 Benchmark Maps Reference

| Benchmark Map | Dimensions | Features | Stress Test Use Case |
|---|---|---|---|
| **Custom Warehouse** | 18 × 24 | 12 shelf blocks, 8 stations | General fulfillment & order handling |
| **warehouse-10-20-10-2-1** | 161 × 63 | Large-scale realistic distribution center | Long-distance path planning (20–50 robots) |
| **maze-32-32-2** | 32 × 32 | Narrow 2-cell corridors | Dense conflict resolution & PIBT pushing |
| **random-32-32-10** | 32 × 32 | 10% random static obstacle density | Dynamic obstacle bypass & detour planning |

---

## 📄 License

This project is licensed under the MIT License.

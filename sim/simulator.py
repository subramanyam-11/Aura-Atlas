import random
import asyncio
from .grid import create_warehouse
from .reservation import ReservationTable
from .robot import Robot, Task, State
from .pibt import pibt_step
from .station import Station
from .predictor import predict_conflicts


class PerformanceTracker:
    def __init__(self):
        self.delivery_times = []
        self.conflicts      = 0
        self.replans        = 0
        self.heatmap        = {}

    def record_delivery(self, t):
        self.delivery_times.append(t)

    def record_conflict(self):
        self.conflicts += 1

    def record_replan(self):
        self.replans += 1

    def visit(self, x, y):
        self.heatmap[(x, y)] = self.heatmap.get((x, y), 0) + 1

    def avg_delivery(self):
        recent = self.delivery_times[-20:]
        return round(sum(recent) / len(recent), 1) if recent else 0

    def throughput_100(self, tick):
        if not tick:
            return 0
        return round(len(self.delivery_times) / tick * 100, 1)

    def heatmap_top(self, n=80):
        if not self.heatmap:
            return []
        mx = max(self.heatmap.values())
        top = sorted(self.heatmap.items(), key=lambda x: -x[1])[:n]
        return [{'x': x, 'y': y, 'v': round(v / mx, 3)} for (x, y), v in top]

    def to_dict(self, tick):
        return {
            'throughput_100':   self.throughput_100(tick),
            'avg_delivery':     self.avg_delivery(),
            'conflicts':        self.conflicts,
            'replans':          self.replans,
            'total_deliveries': len(self.delivery_times),
        }


class Simulator:
    def __init__(self, grid=None, num_robots=5, robot_capacity=1):
        self.grid           = grid or create_warehouse()
        self.res            = ReservationTable()
        self.robots         = []
        self.pending        = []
        self.stations       = []
        self.tick           = 0
        self.running        = False
        self.tick_delay     = 0.3
        self.events         = []
        self.hive_mind      = []
        self.perf           = PerformanceTracker()
        self.robot_capacity = robot_capacity

        Station._counter = 0
        self._init_stations()
        self._spawn(num_robots)

    def _init_stations(self):
        for pos in self.grid.pick_stations:
            self.stations.append(Station(pos[0], pos[1], 'pick'))
        for pos in self.grid.drop_stations:
            self.stations.append(Station(pos[0], pos[1], 'drop'))

    def _station_at(self, pos):
        for s in self.stations:
            if s.x == pos[0] and s.y == pos[1]:
                return s
        return None

    def _spawn(self, n):
        cands = []
        for px, py in self.grid.pick_stations:
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = px + dx, py + dy
                    if self.grid.is_free(x, y):
                        cands.append([x, y])
        if len(cands) < n:
            cands += [[x, y]
                      for y in range(self.grid.height // 2, self.grid.height)
                      for x in range(self.grid.width)
                      if self.grid.is_free(x, y)]
        seen, uniq = set(), []
        for p in cands:
            k = tuple(p)
            if k not in seen:
                seen.add(k)
                uniq.append(p)
        random.shuffle(uniq)
        for i in range(min(n, len(uniq))):
            self.robots.append(Robot(i, uniq[i], capacity=self.robot_capacity))

    # ── Orders ─────────────────────────────────────────────────────────
    def _new_task(self, priority=1, qty=1):
        picks = [s for s in self.stations if s.type == 'pick' and s.can_pickup(qty)]
        drops = [s for s in self.stations if s.type == 'drop' and s.can_drop(qty)]
        if not picks or not drops:
            return None
        pick = random.choices(picks, weights=[s.priority for s in picks], k=1)[0]
        drop = random.choice(drops)
        t = Task([pick.x, pick.y], [drop.x, drop.y], priority, qty)
        t.created_tick    = self.tick
        t.pick_station_id = pick.id
        t.drop_station_id = drop.id
        return t

    def _auction(self, task):
        """Only idle robots (task is None) may accept new orders."""
        eligible = [r for r in self.robots
                    if r.state != State.FAILED and r.task is None]
        return min(eligible, key=lambda r: r.bid(task)) if eligible else None

    def add_order(self, priority=1, qty=1):
        qty  = max(1, min(qty, self.robot_capacity))
        task = self._new_task(priority, qty)
        if task is None:
            self.events.append("No stock available for new order")
            return
        winner = self._auction(task)
        if winner:
            winner.assign(task, self.grid, self.res, self.tick)
            task.assigned_robot = winner.id
            self.events.append(
                f"Order {task.id} ({qty}pkg, p{priority}) → Robot {winner.id}")
        else:
            self.pending.append(task)
            self.events.append(f"Order {task.id} queued (no idle robot)")

    # ── Events ─────────────────────────────────────────────────────────
    def block_cell(self, x, y):
        self.grid.block_cell(x, y)
        self.events.append(f"Cell ({x},{y}) blocked")
        for r in self.robots:
            if r.state == State.MOVING and any(
                    p[0] == x and p[1] == y for p in r.path[r.path_idx:]):
                r.replan(self.grid, self.res, self.tick)
                self.perf.record_replan()
                self.events.append(f"Robot {r.id} replanning around block")

    def fail_robot(self, rid):
        r = next((r for r in self.robots if r.id == rid), None)
        if not r:
            return
        lost = r.task
        r.fail(self.res)
        self.grid.block_cell(r.x, r.y)
        self.events.append(f"Robot {rid} FAILED at ({r.x},{r.y})")
        self.hive_mind.insert(0, {'type': 'fail',
                                   'msg': f'R{rid} FAILED — re-auctioning task'})
        if lost:
            w = self._auction(lost)
            if w:
                w.assign(lost, self.grid, self.res, self.tick)
                self.events.append(f"Task {lost.id} → Robot {w.id}")
                self.hive_mind.insert(0, {'type': 'auction',
                    'msg': f'Task {lost.id} re-auctioned to R{w.id}'})
            else:
                self.pending.append(lost)

    def set_station_priority(self, sid, priority):
        for s in self.stations:
            if s.id == sid:
                s.priority = max(1, min(3, priority))
                self.events.append(f"Station {sid} priority set to {priority}")
                return True
        return False

    # ── Core tick ──────────────────────────────────────────────────────
    def step(self):
        self.events  = []
        new_hive     = []
        self.tick   += 1
        self.res.release_before(self.tick - 1)

        # Assign pending tasks to newly-idle robots
        for r in self.robots:
            if r.task is None and r.state == State.IDLE and self.pending:
                task = self.pending.pop(0)
                r.assign(task, self.grid, self.res, self.tick)
                task.assigned_robot = r.id
                self.events.append(f"Pending task {task.id} → Robot {r.id}")

        # Replan waiting robots
        for r in self.robots:
            if r.state == State.WAITING and r.task and not r.path:
                r.replan(self.grid, self.res, self.tick)

        # Auto-generate orders every 12 ticks
        if self.tick % 12 == 0:
            self.add_order(random.randint(1, 3), random.randint(1, self.robot_capacity))

        # Auto-restock pick stations every 40 ticks
        if self.tick % 40 == 0:
            for s in self.stations:
                if s.type == 'pick' and s.current < s.max_capacity // 2:
                    s.restock(4)
                    new_hive.append({'type': 'restock',
                        'msg': f'Station ({s.x},{s.y}) restocked +4'})

        # Snapshot before step (for event detection)
        pre_tasks    = {r.id: r.task for r in self.robots}
        pre_carrying = {r.id: r.carrying for r in self.robots}

        # PIBT step
        moves, pibt_msgs = pibt_step(self.robots, self.grid)
        for m in pibt_msgs:
            if m['type'] == 'yield':
                self.perf.record_conflict()
        new_hive.extend(pibt_msgs)

        # Apply moves, detect pickup/dropoff events
        for r in self.robots:
            if r.id not in moves:
                continue
            nx, ny = moves[r.id]
            event  = r.apply_move(nx, ny, self.grid, self.res, self.tick)
            self.perf.visit(nx, ny)

            if event == 'pickup_reached':
                task    = r.task           # phase is now 'dropoff', pickup still valid
                station = self._station_at(task.pickup)
                actual  = station.do_pickup(task.qty) if station else task.qty
                r.carrying = actual
                new_hive.append({'type': 'pickup',
                    'msg': f'R{r.id} picks up {actual}pkg at ({task.pickup[0]},{task.pickup[1]})'})
                self.events.append(f"Robot {r.id} picked up {actual} packages")

            elif event == 'dropoff_reached':
                prev  = pre_tasks.get(r.id)
                carry = pre_carrying.get(r.id, 1)
                if prev:
                    duration = self.tick - prev.created_tick
                    self.perf.record_delivery(duration)
                    station  = self._station_at(prev.dropoff)
                    if station:
                        station.do_drop(carry)
                    new_hive.append({'type': 'delivery',
                        'msg': f'R{r.id} delivers {carry}pkg to ({prev.dropoff[0]},{prev.dropoff[1]}) [{duration}t]'})
                    self.events.append(
                        f"Robot {r.id} completed Task {prev.id} ({duration} ticks)")

        self.hive_mind = (new_hive + self.hive_mind)[:30]

    def state_dict(self):
        heatmap = self.perf.heatmap_top(80) if self.tick % 3 == 0 else []
        return {
            'tick':        self.tick,
            'running':     self.running,
            'robots':      [r.to_dict() for r in self.robots],
            'stations':    [s.to_dict() for s in self.stations],
            'hive_mind':   self.hive_mind[:20],
            'conflicts':   predict_conflicts(self.robots),
            'performance': self.perf.to_dict(self.tick),
            'heatmap':     heatmap,
            'events':      self.events,
            'metrics': {
                'throughput': sum(r.done for r in self.robots),
                'active':  sum(1 for r in self.robots if r.state == State.MOVING),
                'idle':    sum(1 for r in self.robots if r.state == State.IDLE),
                'failed':  sum(1 for r in self.robots if r.state == State.FAILED),
            }
        }

    async def run_loop(self, broadcast):
        self.running = True
        try:
            for _ in range(len(self.robots)):
                self.add_order()
            while self.running:
                self.step()
                s = self.state_dict()
                if self.tick <= 2 or self.tick % 30 == 0:
                    s['grid'] = self.grid.to_dict()
                await broadcast(s)
                await asyncio.sleep(self.tick_delay)
        except asyncio.CancelledError:
            self.running = False
            raise
        finally:
            self.running = False

from enum import Enum
from .astar import space_time_astar
import random

class State(Enum):
    IDLE    = "idle"
    MOVING  = "moving"
    WAITING = "waiting"
    FAILED  = "failed"

COLORS = [
    "#4CAF50", "#2196F3", "#FF9800", "#E91E63",
    "#9C27B0", "#00BCD4", "#FF5722", "#607D8B",
    "#F44336", "#00E676", "#FFEA00", "#40C4FF",
]

class Task:
    _counter = 0
    def __init__(self, pickup, dropoff, priority=1, qty=1):
        Task._counter += 1
        self.id             = Task._counter
        self.pickup         = list(pickup)
        self.dropoff        = list(dropoff)
        self.priority       = priority
        self.qty            = qty        # packages per trip
        self.phase          = "pickup"   # "pickup" | "dropoff"
        self.assigned_robot = None
        self.created_tick   = 0
        self.pick_station_id = None
        self.drop_station_id = None

    @property
    def goal(self):
        return self.pickup if self.phase == "pickup" else self.dropoff


class Robot:
    def __init__(self, robot_id, start, capacity=1):
        self.id        = robot_id
        self.x, self.y = start[0], start[1]
        self.color     = COLORS[robot_id % len(COLORS)]
        self.state     = State.IDLE
        self.task      = None
        self.path      = []
        self.path_idx  = 0
        self.done      = 0
        self.capacity  = capacity
        self.carrying  = 0

    @property
    def pos(self):
        return [self.x, self.y]

    def assign(self, task, grid, res, tick):
        """Only call when self.task is None."""
        self.task  = task
        self.state = State.MOVING
        self._plan(grid, res, tick)

    def _plan(self, grid, res, tick):
        if not self.task:
            return
        path = space_time_astar(
            grid, self.pos, self.task.goal,
            res, self.id, start_time=tick
        )
        if path:
            self.path     = path
            self.path_idx = 0
            res.release(self.id)
            for i, (px, py) in enumerate(path):
                res.claim(px, py, tick + i, self.id)
            self.state = State.MOVING
        else:
            self.state = State.WAITING
            res.release(self.id)
            res.claim(self.x, self.y, tick, self.id)
            res.claim(self.x, self.y, tick + 1, self.id)

    def replan(self, grid, res, tick):
        if self.task and self.state != State.FAILED:
            self._plan(grid, res, tick)

    def apply_move(self, nx, ny, grid, res, tick):
        """
        Apply one PIBT step.
        Returns: None | 'pickup_reached' | 'dropoff_reached'
        """
        if self.state in (State.IDLE, State.FAILED):
            return None

        moved = (nx != self.x or ny != self.y)
        self.x, self.y = nx, ny

        if moved:
            self.state = State.MOVING
            if (self.path and
                    self.path_idx + 1 < len(self.path) and
                    [nx, ny] == list(self.path[self.path_idx + 1])):
                self.path_idx += 1
            else:
                # PIBT deviated from A* — clear so we replan next tick
                self.path     = []
                self.path_idx = 0
        else:
            self.state = State.WAITING

        if not self.task:
            return None

        if [self.x, self.y] == self.task.goal:
            if self.task.phase == "pickup":
                self.task.phase = "dropoff"
                self._plan(grid, res, tick + 1)
                self.state = State.MOVING
                return "pickup_reached"
            else:
                self.done     += 1
                self.task      = None
                self.state     = State.IDLE
                self.path      = []
                self.carrying  = 0
                res.release(self.id)
                return "dropoff_reached"

        if self.task and not self.path:
            self._plan(grid, res, tick + 1)

        return None

    def fail(self, res):
        self.state    = State.FAILED
        self.carrying = 0
        res.release(self.id)

    def bid(self, task):
        d = abs(self.x - task.pickup[0]) + abs(self.y - task.pickup[1])
        return (d + random.uniform(0, 0.5)) / task.priority

    def to_dict(self):
        return {
            'id':       self.id,
            'x':        self.x,
            'y':        self.y,
            'color':    self.color,
            'state':    self.state.value,
            'phase':    self.task.phase if self.task else None,
            'task_id':  self.task.id    if self.task else None,
            'target':   list(self.task.goal) if self.task else None,
            'pickup':   self.task.pickup if self.task else None,
            'dropoff':  self.task.dropoff if self.task else None,
            'carrying': self.carrying,
            'capacity': self.capacity,
            'path':     self.path[self.path_idx:],
            'done':     self.done,
        }

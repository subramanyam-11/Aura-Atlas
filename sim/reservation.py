class ReservationTable:
    def __init__(self):
        self._table = {}   # (x,y,t) -> robot_id
        self._owned = {}   # robot_id -> set of keys

    def claim(self, x, y, t, robot_id):
        key = (x, y, t)
        self._table[key] = robot_id
        self._owned.setdefault(robot_id, set()).add(key)

    def is_reserved(self, x, y, t, ignore=None):
        v = self._table.get((x, y, t))
        return v is not None and v != ignore

    def is_swap_conflict(self, x1, y1, x2, y2, t, ignore=None):
        occ_t  = self._table.get((x2, y2, t))
        occ_t1 = self._table.get((x1, y1, t+1))
        if occ_t is None or occ_t == ignore:
            return False
        return occ_t == occ_t1

    def release(self, robot_id):
        for k in self._owned.pop(robot_id, set()):
            self._table.pop(k, None)

    def release_before(self, t):
        stale = [k for k in self._table if k[2] < t]
        for k in stale:
            rid = self._table.pop(k)
            self._owned.get(rid, set()).discard(k)

class Station:
    _counter = 0

    def __init__(self, x, y, stype, capacity=12):
        Station._counter += 1
        self.id           = Station._counter
        self.x, self.y    = x, y
        self.type         = stype      # 'pick' | 'drop'
        self.max_capacity = capacity
        self.current      = capacity if stype == 'pick' else 0
        self.priority     = 1          # 1-3, user-configurable

    def can_pickup(self, qty=1):
        return self.current >= qty

    def can_drop(self, qty=1):
        return (self.max_capacity - self.current) >= qty

    def do_pickup(self, qty=1):
        actual = min(qty, self.current)
        self.current -= actual
        return actual

    def do_drop(self, qty=1):
        actual = min(qty, self.max_capacity - self.current)
        self.current += actual
        return actual

    def restock(self, qty=4):
        self.current = min(self.max_capacity, self.current + qty)
        return qty

    def to_dict(self):
        return {
            'id': self.id,
            'x': self.x,
            'y': self.y,
            'type': self.type,
            'current': self.current,
            'max': self.max_capacity,
            'priority': self.priority,
            'pct': round(self.current / self.max_capacity * 100) if self.max_capacity else 0
        }

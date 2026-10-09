import numpy as np
from typing import List

OBSTACLE, FREE = 1, 0

class Grid:
    def __init__(self, width, height, cells, pick_stations=None, drop_stations=None):
        self.width          = width
        self.height         = height
        self.cells          = cells.copy()
        self.pick_stations  = pick_stations or []
        self.drop_stations  = drop_stations or []

    def is_free(self, x, y):
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return False
        return self.cells[y][x] == FREE

    def block_cell(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.cells[y][x] = OBSTACLE

    def get_neighbors(self, x, y):
        return [(x+dx, y+dy) for dx, dy in [(0,1),(0,-1),(1,0),(-1,0)]
                if self.is_free(x+dx, y+dy)]

    def to_dict(self):
        return {
            'width':         self.width,
            'height':        self.height,
            'cells':         self.cells.tolist(),
            'pick_stations': self.pick_stations,
            'drop_stations': self.drop_stations,
        }


def create_warehouse(shelf_rows=3, shelf_cols=4, shelf_len=4,
                     shelf_w=2, aisle=2):
    col_stride = shelf_w + aisle
    row_stride = shelf_len + aisle
    border = 1
    W = border + shelf_cols * col_stride + border
    H = border + 2 + aisle + shelf_rows * row_stride + border
    cells = np.zeros((H, W), dtype=int)
    shelf_y0 = border + 2 + aisle
    for r in range(shelf_rows):
        for c in range(shelf_cols):
            y0 = shelf_y0 + r * row_stride
            x0 = border + c * col_stride
            cells[y0:y0+shelf_len, x0:x0+shelf_w] = OBSTACLE
    picks, drops = [], []
    for c in range(shelf_cols):
        cx = border + c * col_stride + shelf_w // 2
        drops.append([cx, border])
        picks.append([cx, H - border - 1])
    return Grid(W, H, cells, picks, drops)


def load_movingai_map(filepath: str) -> Grid:
    with open(filepath) as f:
        lines = f.readlines()
    h = int(next(l for l in lines if l.startswith('height')).split()[1])
    w = int(next(l for l in lines if l.startswith('width')).split()[1])
    start = next(i for i, l in enumerate(lines) if l.strip() == 'map') + 1
    cells = np.zeros((h, w), dtype=int)
    for y, line in enumerate(lines[start:start + h]):
        for x, ch in enumerate(line.rstrip()):
            if ch in ('@', 'T', 'O', 'S'):
                cells[y][x] = OBSTACLE
    return Grid(w, h, cells)


def auto_stations(grid: Grid, count: int = 8):
    """
    Scan the top rows for drop stations and bottom rows for pick stations.
    Spreads them evenly so robots don't all converge on one point.
    """
    def scan_row(y_range):
        for y in y_range:
            row = [[x, y] for x in range(grid.width) if grid.is_free(x, y)]
            if row:
                step = max(1, len(row) // count)
                return row[::step][:count]
        return []

    picks = scan_row(range(grid.height - 1, grid.height // 2, -1))
    drops = scan_row(range(0, grid.height // 2))

    if not picks:
        all_free = [[x, y] for y in range(grid.height - 1, -1, -1) for x in range(grid.width) if grid.is_free(x, y)]
        picks = all_free[:count] if all_free else [[0, 0]]
    if not drops:
        all_free = [[x, y] for y in range(grid.height) for x in range(grid.width) if grid.is_free(x, y)]
        drops = all_free[:count] if all_free else [[0, 0]]

    return picks, drops

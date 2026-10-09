import heapq

def heuristic(a, b):
    return abs(a[0]-b[0]) + abs(a[1]-b[1])

def space_time_astar(grid, start, goal, reservation, robot_id,
                     start_time=0, max_time=250):
    if list(start) == list(goal):
        return [list(start)]

    open_set = [(heuristic(start, goal), 0, start_time, start[0], start[1])]
    came_from = {}
    g_score = {(start[0], start[1], start_time): 0}
    max_horizon = start_time + max_time

    while open_set:
        _, g, t, x, y = heapq.heappop(open_set)
        if (x, y) == (goal[0], goal[1]):
            path = []
            state = (x, y, t)
            while state in came_from:
                path.append([state[0], state[1]])
                state = came_from[state]
            path.append(list(start))
            return path[::-1]
        if t >= max_horizon:
            continue
        if g > g_score.get((x, y, t), float('inf')):
            continue

        for nx, ny in grid.get_neighbors(x, y) + [(x, y)]:  # wait in place too
            nt = t + 1
            if reservation.is_reserved(nx, ny, nt, ignore=robot_id):
                continue
            if reservation.is_swap_conflict(x, y, nx, ny, t, ignore=robot_id):
                continue
            ng = g + 1
            state = (nx, ny, nt)
            if ng < g_score.get(state, float('inf')):
                g_score[state] = ng
                heapq.heappush(open_set, (ng + heuristic((nx, ny), goal), ng, nt, nx, ny))
                came_from[state] = (x, y, t)
    return None

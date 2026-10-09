"""
PIBT — Priority Inheritance with Backtracking (Okumura et al., 2022)
One-step decentralised conflict resolution layered on top of A* guidance.
"""

def pibt_step(robots_list, grid):
    """
    Returns (moves: {robot_id: [nx,ny]}, messages: [{type, msg}])
    """
    active = {r.id: r for r in robots_list
              if r.state.value in ('moving', 'waiting')}
    if not active:
        return {}, []

    messages = []

    def base_priority(r):
        if r.task is None:
            return 0
        gx, gy = r.task.goal
        return r.task.priority * 10000 - (abs(r.x - gx) + abs(r.y - gy))

    priorities = {rid: base_priority(r) for rid, r in active.items()}
    cur_pos    = {(r.x, r.y): r.id for r in robots_list}
    result     = {}
    claimed    = {}
    in_call    = set()

    def try_move(rid, depth=0):
        if rid in result:
            return True
        if depth > len(active) + 2:
            r = active[rid]
            result[rid] = [r.x, r.y]
            return False

        r = active[rid]
        in_call.add(rid)

        for nx, ny in _candidates(r, grid):
            c = (nx, ny)
            if c in claimed and priorities[claimed[c]] > priorities[rid]:
                continue

            occ = cur_pos.get(c)
            if occ is not None and occ != rid:
                if occ not in active:
                    continue
                if occ in result:
                    if result[occ] != list(c):
                        result[rid] = list(c)
                        claimed[c] = rid
                        in_call.discard(rid)
                        return True
                    else:
                        continue
                if occ in in_call:
                    continue
                old = priorities[occ]
                priorities[occ] = priorities[rid] - 0.5
                if try_move(occ, depth + 1) and result.get(occ) != list(c):
                    messages.append({'type': 'yield',
                                     'msg':  f'R{occ} yields to R{rid}'})
                    result[rid] = list(c)
                    claimed[c] = rid
                    in_call.discard(rid)
                    return True
                priorities[occ] = old
            else:
                result[rid] = list(c)
                claimed[c] = rid
                in_call.discard(rid)
                return True

        result[rid] = [r.x, r.y]
        claimed[(r.x, r.y)] = rid
        in_call.discard(rid)
        return False

    for rid in sorted(active, key=lambda i: -priorities[i]):
        if rid not in result:
            in_call.clear()
            try_move(rid)

    # Detect A* deviations
    for rid, move in result.items():
        r = active[rid]
        if r.path and r.path_idx + 1 < len(r.path):
            planned = list(r.path[r.path_idx + 1])
            if move != planned and move != [r.x, r.y]:
                messages.append({'type': 'detour',
                                 'msg':  f'R{rid} selects alternate route'})

    return result, messages


def _candidates(robot, grid):
    seen, out = set(), []
    def add(x, y):
        if (x, y) not in seen and grid.is_free(x, y):
            seen.add((x, y))
            out.append((x, y))

    if robot.path and robot.path_idx + 1 < len(robot.path):
        add(*robot.path[robot.path_idx + 1])

    if robot.task:
        gx, gy = robot.task.goal
        for nx, ny in sorted(grid.get_neighbors(robot.x, robot.y),
                             key=lambda p: abs(p[0] - gx) + abs(p[1] - gy)):
            add(nx, ny)

    out.append((robot.x, robot.y))
    return out

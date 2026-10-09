def predict_conflicts(robots, lookahead=8):
    """
    Scan planned paths for vertex and swap conflicts.
    Returns up to 5 predictions sorted by urgency.
    """
    active = [r for r in robots
              if r.state.value in ('moving', 'waiting') and r.path]
    conflicts = []

    for i, r1 in enumerate(active):
        p1 = r1.path[r1.path_idx: r1.path_idx + lookahead]
        for r2 in active[i+1:]:
            p2 = r2.path[r2.path_idx: r2.path_idx + lookahead]
            n  = min(len(p1), len(p2))
            for step in range(n):
                # Vertex conflict
                if list(p1[step]) == list(p2[step]):
                    conflicts.append({
                        'robot_a': r1.id,
                        'robot_b': r2.id,
                        'cell': list(p1[step]),
                        'ticks_away': step + 1,
                        'type': 'vertex',
                        'confidence': round(max(0.2, 1.0 - step * 0.1), 2)
                    })
                    break
                # Swap conflict
                if (step > 0 and
                        list(p1[step]) == list(p2[step-1]) and
                        list(p2[step]) == list(p1[step-1])):
                    conflicts.append({
                        'robot_a': r1.id,
                        'robot_b': r2.id,
                        'cell': list(p1[step]),
                        'ticks_away': step,
                        'type': 'swap',
                        'confidence': 0.95
                    })
                    break

    conflicts.sort(
        key=lambda c: c['confidence'] / max(1, c['ticks_away']),
        reverse=True
    )
    return conflicts[:5]

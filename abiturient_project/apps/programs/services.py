def get_chance(user_score, program):
    """Возвращает прогноз поступления."""
    diff = user_score - program.min_score
    if user_score == 0:
        return None
    if diff >= 30:
        return {'label': 'Высокие шансы', 'css': 'success', 'pct': min(95, 70 + diff)}
    if diff >= 10:
        return {'label': 'Хорошие шансы', 'css': 'good', 'pct': min(70, 55 + diff)}
    if diff >= 0:
        return {'label': 'Средние шансы', 'css': 'warning', 'pct': max(30, 40 + diff)}
    if diff >= -20:
        return {'label': 'Низкие шансы', 'css': 'danger', 'pct': max(5, 25 + diff)}
    return {'label': 'Не проходите', 'css': 'fail', 'pct': 0}


def match_programs(user, programs):
    results = []
    score_map = {
        er.subject_id: er.score
        for er in user.exam_results.select_related('subject').all()
    }
    for program in programs.prefetch_related('subjects'):
        relevant_scores = [
            score_map[s.id]
            for s in program.subjects.all()
            if s.id in score_map
        ]
        if not relevant_scores:
            continue
        user_total = sum(relevant_scores)
        chance = get_chance(user_total, program)
        results.append({
            'program': program,
            'user_total': user_total,
            'chance': chance,
            'gap': user_total - program.min_score,
        })
    results.sort(key=lambda x: x['chance']['pct'] if x['chance'] else 0, reverse=True)
    return results
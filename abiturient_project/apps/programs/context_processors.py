def compare_count(request):
    compare = request.session.get('compare', [])
    return {'compare_count': len(compare)}
from utils.text_utils import is_project_question, is_bagua_question, is_algorithm_question, classify_bagua_category


def classify_question(text: str) -> dict:
    classification = {
        'type': '',
        'category': '',
        'confidence': 0.0
    }
    
    scores = {
        'project': 0,
        'bagua': 0,
        'algorithm': 0
    }
    
    if is_project_question(text):
        scores['project'] += 3
    if is_bagua_question(text):
        scores['bagua'] += 2
    if is_algorithm_question(text):
        scores['algorithm'] += 3
    
    max_score = max(scores.values())
    total_score = sum(scores.values())
    
    if max_score == 0:
        classification['type'] = 'bagua'
        classification['confidence'] = 0.5
    else:
        classification['type'] = max(scores, key=scores.get)
        classification['confidence'] = max_score / total_score if total_score > 0 else 0.0
    
    if classification['type'] == 'bagua':
        classification['category'] = classify_bagua_category(text)
    elif classification['type'] == 'algorithm':
        classification['category'] = 'algorithm'
    else:
        classification['category'] = 'project'
    
    return classification
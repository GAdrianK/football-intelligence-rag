from app.services.query_classifier import QueryClassifier

def test_greeting_classification():
    classifier = QueryClassifier()
    res = classifier.classify("salut")
    assert res["type"] == "greeting"
    
    res = classifier.classify("Bonjour, comment ça va ?")
    assert res["type"] == "greeting"

def test_out_of_scope_classification():
    classifier = QueryClassifier()
    res = classifier.classify("Comment faire une pizza margherita ?")
    assert res["type"] == "out_of_scope"
    
    res = classifier.classify("Quelle est la météo à Paris ?")
    assert res["type"] == "out_of_scope"

def test_tactical_question_classification():
    classifier = QueryClassifier()
    res = classifier.classify("Comment défendre en bloc bas ?")
    assert res["type"] == "tactical_question"
    assert res["intent"] == "defend"
    assert res["phase"] == "defensive"
    
    res = classifier.classify("Quels sont les principes pour attaquer un bloc bas ?")
    assert res["type"] == "tactical_question"
    assert res["intent"] == "attack"
    assert res["phase"] == "offensive"

    res = classifier.classify("Explique-moi ce qu'est un faux 9")
    assert res["type"] == "tactical_question"
    assert res["intent"] == "roles"

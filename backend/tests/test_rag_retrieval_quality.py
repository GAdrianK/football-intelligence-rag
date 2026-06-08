import pytest
from app.services.rag_engine import RAGEngine
from app.services.query_classifier import QueryClassifier
from app.core.config import settings

def test_rag_retrieval_quality_defend_vs_attack():
    engine = RAGEngine(
        knowledge_base_dir=settings.get_kb_dir(),
        openai_api_key="mock-testing-key"
    )
    engine.initialize()
    classifier = QueryClassifier()

    # 1. Tester "comment défendre un bloc bas ?"
    query_defend = "comment défendre un bloc bas ?"
    classif_defend = classifier.classify(query_defend)
    assert classif_defend["intent"] == "defend"
    
    results_defend = engine.search(query_defend, top_k=5, query_metadata=classif_defend)
    assert len(results_defend) > 0
    
    # Les premiers résultats doivent provenir de bloc_bas.md, transition_defensive_repli.md ou analyse_video_coulissement_bloc.md
    top_sources_defend = [res["source"] for res in results_defend[:2]]
    assert any(src in ["bloc_bas.md", "transition_defensive_repli.md", "analyse_video_coulissement_bloc.md", "analyse_video_cpa_defensifs.md"] for src in top_sources_defend)
    
    # Et le premier résultat ne doit pas être un document d'attaque pur
    assert results_defend[0]["source"] != "principe_desequilibrer_bloc_bas.md"

    # 2. Tester "comment attaquer un bloc bas ?"
    query_attack = "comment attaquer un bloc bas ?"
    classif_attack = classifier.classify(query_attack)
    assert classif_attack["intent"] == "attack"
    
    results_attack = engine.search(query_attack, top_k=5, query_metadata=classif_attack)
    assert len(results_attack) > 0
    
    top_sources_attack = [res["source"] for res in results_attack[:2]]
    assert any(src in ["principe_desequilibrer_bloc_bas.md", "phase_offensive_jeu_couloirs.md", "phase_offensive_centres_surface.md", "phase_offensive_fixation_axiale.md"] for src in top_sources_attack)
    
    # Et le premier résultat ne doit pas être un document de défense pur
    assert results_attack[0]["source"] not in ["bloc_bas.md", "transition_defensive_repli.md"]

def test_rag_retrieval_specific_topics():
    engine = RAGEngine(
        knowledge_base_dir=settings.get_kb_dir(),
        openai_api_key="mock-testing-key"
    )
    engine.initialize()
    classifier = QueryClassifier()

    # "comment sortir du pressing haut ?" -> sortie_balle.md ou relance
    q1 = "comment sortir du pressing haut ?"
    res1 = engine.search(q1, top_k=3, query_metadata=classifier.classify(q1))
    assert any(src in ["sortie_balle.md", "formation_433.md", "formation_343.md", "roles_modernes.md"] for src in [r["source"] for r in res1])

    # "explique-moi un faux 9" -> roles_modernes.md ou rôles/formations
    q2 = "explique-moi un faux 9"
    res2 = engine.search(q2, top_k=3, query_metadata=classifier.classify(q2))
    assert any(src in ["roles_modernes.md", "formation_433.md", "formation_343.md"] for src in [r["source"] for r in res2])

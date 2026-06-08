import pytest
from app.services.rag_engine import RAGEngine
from app.services.chat_service import ChatService
from app.schemas.chat import ChatRequest, ChatMode
from app.core.config import settings

@pytest.fixture
def rag_engine():
    engine = RAGEngine(
        knowledge_base_dir=settings.get_kb_dir(),
        openai_api_key="mock-key"
    )
    engine.initialize()
    return engine

def test_chat_service_initialization(rag_engine):
    service = ChatService(rag_engine=rag_engine, openai_api_key="mock-key")
    # Vérifier que les 3 prompts ont bien été chargés
    assert ChatMode.COACH in service.prompts
    assert ChatMode.ANALYST in service.prompts
    assert ChatMode.FAN in service.prompts
    assert len(service.prompts[ChatMode.COACH]) > 0

def test_chat_service_generate_mock_response(rag_engine):
    service = ChatService(rag_engine=rag_engine, openai_api_key="mock-key")
    
    # Test en mode coach
    req_coach = ChatRequest(message="Comment bloquer une relance basse ?", mode=ChatMode.COACH)
    resp_coach = service.generate_response(req_coach)
    
    assert resp_coach.mode == ChatMode.COACH
    assert "Analyse du Coach" in resp_coach.answer
    assert len(resp_coach.sources) > 0
    
    # Test en mode analyste
    req_analyst = ChatRequest(message="Quels sont les rôles tactiques du double pivot ?", mode=ChatMode.ANALYST)
    resp_analyst = service.generate_response(req_analyst)
    
    assert resp_analyst.mode == ChatMode.ANALYST
    assert "Observations Structurelles" in resp_analyst.answer
    
    # Test en mode fan
    req_fan = ChatRequest(message="Le pressing haut c'est quoi ?", mode=ChatMode.FAN)
    resp_fan = service.generate_response(req_fan)
    
    assert resp_fan.mode == ChatMode.FAN
    assert "L'Avis du Virage" in resp_fan.answer

from types import SimpleNamespace

import pytest

from api.v1 import chat as chat_api
from schemas.chat_schema import ChatRequest
from services.chat_orchestrator import ChatOrchestrator
from services.llm.base import BaseLLMProvider
from services.session import session_manager
from services.session.state import PendingChat


class FakeRetriever:
    calls = 0

    def __init__(self, session, llm):
        self.session = session
        self.llm = llm

    async def retrieve(self, user_id: str, query: str, top_k: int = 5):
        type(self).calls += 1
        return [
            {
                "category": SimpleNamespace(
                    category_name="Career",
                    content="The user is considering counseling as a career.",
                ),
                "resource": None,
                "score": 0.91,
                "strategy": "category_vector",
            }
        ]


class FakeLLM(BaseLLMProvider):
    async def generate_chat_response(self, system_prompt: str, context: str, user_query: str) -> str:
        return "answer"

    async def get_embedding(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    async def extract_memory_intent(
        self,
        text: str,
        categories: list[dict],
        assistant_response: str = "",
        reference_time: str | None = None,
        target_category_name: str | None = None,
    ) -> dict:
        return {}

    async def count_tokens(self, text: str) -> int:
        return 10

    async def generate_stream_response(self, system_prompt: str, context: str, user_query: str):
        yield "answer"


@pytest.mark.asyncio
async def test_orchestrator_context_order_and_trace_contract():
    FakeRetriever.calls = 0
    llm = FakeLLM()
    orchestrator = ChatOrchestrator(
        session=object(),
        llm=llm,
        retriever_factory=FakeRetriever,
    )

    built = await orchestrator.build_context(
        user_id="user-1",
        user_query="What career is the user considering?",
        user_prompt_template="The user's name is Caroline.",
        agent_persona_template="Be concise.",
        pending_chats=[
            PendingChat(user_input="Hi", assistant_response="Hello"),
        ],
        top_k=5,
    )

    assert built.user_query == "What career is the user considering?"
    assert built.context.index("# Recent Conversation") < built.context.index("# Retrieved Memories")
    assert "User: Hi" in built.context
    assert "The user is considering counseling as a career." in built.context
    assert built.trace.retrieved_results[0]["strategy"] == "category_vector"
    assert built.trace.retrieved_context.startswith("# Retrieved Memories")
    assert "When answering, prioritize information in this order" in built.system_prompt
    assert "LANGUAGE RULE (HIGHEST PRIORITY)" in built.system_prompt
    assert "You MUST respond in the SAME language as the user's current message" in built.system_prompt
    assert FakeRetriever.calls == 1


@pytest.mark.asyncio
async def test_orchestrator_can_reuse_injected_retrieval_results_without_second_retrieve():
    FakeRetriever.calls = 0
    llm = FakeLLM()
    orchestrator = ChatOrchestrator(
        session=object(),
        llm=llm,
        retriever_factory=FakeRetriever,
    )

    injected_results = [
        {
            "category": SimpleNamespace(
                category_name="Career",
                content="The user is considering counseling as a career.",
            ),
            "resource": None,
            "score": 0.91,
            "strategy": "category_vector",
        }
    ]

    built = await orchestrator.build_context(
        user_id="user-1",
        user_query="What career is the user considering?",
        retrieved_results=injected_results,
        pending_chats=[],
        top_k=5,
    )

    assert FakeRetriever.calls == 0
    assert built.trace.retrieved_results == injected_results
    assert "The user is considering counseling as a career." in built.context


@pytest.mark.asyncio
async def test_orchestrator_keeps_atomic_category_fact_with_resource_summary():
    llm = FakeLLM()
    orchestrator = ChatOrchestrator(
        session=object(),
        llm=llm,
        retriever_factory=FakeRetriever,
    )

    injected_results = [
        {
            "category": SimpleNamespace(
                category_name="Episodic Memory",
                content="The user asked to forget that they attend pottery workshops for kids.",
            ),
            "resource": SimpleNamespace(
                description=(
                    "The user asked for creative ways to make hands-on activities "
                    "safe and engaging for children."
                ),
            ),
            "score": 0.42,
            "strategy": "category_source_expansion",
        }
    ]

    built = await orchestrator.build_context(
        user_id="user-1",
        user_query="What activities should I suggest?",
        retrieved_results=injected_results,
        pending_chats=[],
    )

    assert "## Most Relevant Memories" in built.trace.retrieved_context
    assert "fact: The user asked to forget that they attend pottery workshops for kids." in built.context
    assert "source_summary: The user asked for creative ways" in built.context


@pytest.mark.asyncio
async def test_orchestrator_prioritizes_category_source_and_high_constraint_memories():
    llm = FakeLLM()
    orchestrator = ChatOrchestrator(
        session=object(),
        llm=llm,
        retriever_factory=FakeRetriever,
    )

    injected_results = [
        {
            "category": None,
            "resource": SimpleNamespace(description="Generic drawing memory."),
            "score": 0.80,
            "strategy": "resource_vector",
        },
        {
            "category": SimpleNamespace(
                category_name="Core Self",
                content="The user has a health constraint related to a past appendectomy.",
            ),
            "resource": SimpleNamespace(description="The user wrote about a surgery at age 6."),
            "score": 0.40,
            "strategy": "category_source_expansion",
        },
        {
            "category": SimpleNamespace(
                category_name="Episodic Memory",
                content="The user asked for movie night ideas.",
            ),
            "resource": None,
            "score": 0.50,
            "strategy": "category_vector",
        },
    ]

    built = await orchestrator.build_context(
        user_id="user-1",
        user_query="Any workout advice?",
        retrieved_results=injected_results,
        pending_chats=[],
    )

    context = built.trace.retrieved_context
    assert context.index("past appendectomy") < context.index("movie night ideas")
    assert context.index("movie night ideas") < context.index("Generic drawing memory")
    assert "## Other Retrieved Memories" in context


@pytest.mark.asyncio
async def test_chat_api_stream_does_not_expose_retrieved_trace(monkeypatch):
    user = SimpleNamespace(
        id="user-chat-contract",
        username="contract-user",
        llm_provider=None,
        llm_api_key=None,
        llm_base_url=None,
        llm_model=None,
        user_prompt_template="The user's name is Caroline.",
        agent_persona_template="Be concise.",
    )

    class FakeUserRepository:
        def __init__(self, session):
            self.session = session

        async def get_by_id(self, user_id):
            return user

    class FakeSession:
        async def get(self, model, item_id):
            return user

    class FakeChatOrchestrator:
        def __init__(self, session, llm):
            self.session = session
            self.llm = llm

        async def stream(self, **kwargs):
            yield "hello"

    monkeypatch.setattr(chat_api, "UserRepository", FakeUserRepository)
    monkeypatch.setattr(chat_api, "ChatOrchestrator", FakeChatOrchestrator)
    monkeypatch.setattr("services.llm.factory.LLMFactory.get_provider", lambda: FakeLLM())

    session_id = "contract-chat-session"
    session_manager.destroy_session(session_id)

    response = await chat_api.chat(
        ChatRequest(
            session_id=session_id,
            query="What should I do next?",
            user_id=user.id,
            modality="text",
        ),
        FakeSession(),
    )

    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
    body = "".join(chunks)

    assert '"type": "content"' in body
    assert '"type": "done"' in body
    assert "retrieved_trace" not in body
    assert "retrieved_results" not in body

    session_manager.destroy_session(session_id)

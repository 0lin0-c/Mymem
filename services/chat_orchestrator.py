import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from services.llm.base import BaseLLMProvider
from services.retrieval.retriever import MemoryRetriever
from services.session.state import PendingChat

logger = logging.getLogger(__name__)

HIGH_CONSTRAINT_MEMORY_TERMS = (
    "forget",
    "forgot",
    "erase",
    "delete",
    "retract",
    "retraction",
    "negation",
    "do not remember",
    "don't remember",
    "no longer",
    "updated",
    "update",
    "sensitive",
    "credit card",
    "card number",
    "address",
    "email",
    "phone",
    "id number",
    "real id",
    "health",
    "medical",
    "allergy",
    "allergies",
    "asthma",
    "inhaler",
    "concussion",
    "surgery",
    "appendectomy",
)


MEMORY_PRIORITY_RULES = """When answering, prioritize information in this order:
1. The user's current message.
2. Relevant retrieved memories.
3. Stable user profile.
4. Assistant persona and style.

Use retrieved memories when they help answer the current message.
If the user's current message updates or contradicts older information, follow the current message.
Do not infer the user's current intent only from profile interests.
Treat explicit forget/delete/retraction/update memories as high-priority constraints over older memories.
When a retrieved atomic memory and its source summary are both available, use the atomic memory as the primary fact and the source summary only as supporting context.

LANGUAGE RULE (HIGHEST PRIORITY):
- You MUST respond in the SAME language as the user's current message. This is a strict requirement, not a suggestion.
- If the user writes in English, your ENTIRE response MUST be in English. Never use Chinese.
- If the user writes in Chinese, your ENTIRE response MUST be in Chinese.
- Do NOT switch response language because profile, persona, or retrieved memories use another language.
- Preserve proper nouns and quoted terms in their original language."""


@dataclass
class ChatOrchestratorTrace:
    retrieved_results: list[dict[str, Any]] = field(default_factory=list)
    retrieved_context: str = ""
    recent_context: str = ""
    context: str = ""


@dataclass
class ChatOrchestratorContext:
    system_prompt: str
    context: str
    user_query: str
    trace: ChatOrchestratorTrace


class ChatOrchestrator:
    """Builds production chat context and streams LLM responses."""

    def __init__(
        self,
        session: AsyncSession,
        llm: BaseLLMProvider,
        retriever_factory: Callable[[AsyncSession, BaseLLMProvider], MemoryRetriever] = MemoryRetriever,
    ):
        self.session = session
        self.llm = llm
        self.retriever_factory = retriever_factory

    async def build_context(
        self,
        *,
        user_id: str,
        user_query: str,
        user_prompt_template: str | None = None,
        agent_persona_template: str | None = None,
        pending_chats: Sequence[PendingChat] | None = None,
        top_k: int = 15,
        max_retrieved_tokens: int = 2000,
        retrieved_results: Sequence[dict[str, Any]] | None = None,
        retrieved_context: str | None = None,
    ) -> ChatOrchestratorContext:
        system_prompt = self._build_system_prompt(
            user_prompt_template=user_prompt_template,
            agent_persona_template=agent_persona_template,
        )
        recent_context = self._build_recent_context(pending_chats or [])
        effective_results = list(retrieved_results) if retrieved_results is not None else await self._retrieve(
            user_id=user_id,
            query=user_query,
            top_k=top_k,
        )
        effective_retrieved_context = retrieved_context
        if effective_retrieved_context is None:
            effective_retrieved_context = await self._build_retrieved_context(
                effective_results,
                max_tokens=max_retrieved_tokens,
            )
        context = self._join_context(recent_context, effective_retrieved_context)

        trace = ChatOrchestratorTrace(
            retrieved_results=effective_results,
            retrieved_context=effective_retrieved_context,
            recent_context=recent_context,
            context=context,
        )
        return ChatOrchestratorContext(
            system_prompt=system_prompt,
            context=context,
            user_query=user_query,
            trace=trace,
        )

    async def stream(
        self,
        *,
        user_id: str,
        user_query: str,
        user_prompt_template: str | None = None,
        agent_persona_template: str | None = None,
        pending_chats: Sequence[PendingChat] | None = None,
        top_k: int = 15,
        max_retrieved_tokens: int = 2000,
        retrieved_results: Sequence[dict[str, Any]] | None = None,
        retrieved_context: str | None = None,
    ) -> AsyncGenerator[str, None]:
        context = await self.build_context(
            user_id=user_id,
            user_query=user_query,
            user_prompt_template=user_prompt_template,
            agent_persona_template=agent_persona_template,
            pending_chats=pending_chats,
            top_k=top_k,
            max_retrieved_tokens=max_retrieved_tokens,
            retrieved_results=retrieved_results,
            retrieved_context=retrieved_context,
        )
        async for chunk in self.llm.generate_stream_response(
            system_prompt=context.system_prompt,
            context=context.context,
            user_query=context.user_query,
        ):
            yield chunk

    def _build_system_prompt(
        self,
        *,
        user_prompt_template: str | None,
        agent_persona_template: str | None,
    ) -> str:
        parts = []
        if user_prompt_template:
            parts.append(user_prompt_template)
        if agent_persona_template:
            parts.append(agent_persona_template)
        if not parts:
            parts.append("You are a friendly intelligent assistant.")
        parts.append(MEMORY_PRIORITY_RULES)
        return "\n\n".join(parts)

    def _build_recent_context(self, pending_chats: Sequence[PendingChat]) -> str:
        recent_chats = list(pending_chats)[-5:]
        if not recent_chats:
            return ""
        lines = ["# Recent Conversation"]
        for chat in recent_chats:
            lines.append(f"User: {chat.user_input}")
            lines.append(f"Assistant: {chat.assistant_response}")
        return "\n".join(lines)

    async def _retrieve(self, *, user_id: str, query: str, top_k: int) -> list[dict[str, Any]]:
        try:
            retriever = self.retriever_factory(self.session, self.llm)
            return await retriever.retrieve(user_id=user_id, query=query, top_k=top_k)
        except Exception as exc:
            logger.warning("Memory retrieval failed during chat orchestration: %s", exc)
            return []

    async def _build_retrieved_context(
        self,
        results: list[dict[str, Any]],
        max_tokens: int,
    ) -> str:
        if not results:
            return ""

        prioritized_results = self._prioritize_retrieved_results(results)
        lines = ["# Retrieved Memories", "## Most Relevant Memories"]
        current_tokens = 0
        emitted = 0

        for output_index, (result, is_priority) in enumerate(prioritized_results, start=1):
            if not is_priority and "## Other Retrieved Memories" not in lines:
                if emitted == 0:
                    lines.pop()
                lines.append("## Other Retrieved Memories")

            line = self._format_retrieved_result(output_index, result)
            if not line:
                continue
            try:
                line_tokens = await self.llm.count_tokens(line)
            except Exception:
                line_tokens = len(line) // 4
            if current_tokens + line_tokens > max_tokens:
                break

            lines.append(line)
            current_tokens += line_tokens
            emitted += 1

        return "\n".join(lines) if emitted else ""

    def _prioritize_retrieved_results(
        self,
        results: Sequence[dict[str, Any]],
    ) -> list[tuple[dict[str, Any], bool]]:
        ranked: list[tuple[tuple[int, int, int, int], dict[str, Any], bool]] = []
        for original_index, result in enumerate(results):
            strategy = result.get("strategy")
            has_category = result.get("category") is not None
            high_constraint = self._is_high_constraint_memory(result)
            is_priority = (
                strategy == "category_source_expansion"
                or has_category
                or high_constraint
            )
            rank_key = (
                0 if strategy == "category_source_expansion" else 1,
                0 if has_category else 1,
                0 if high_constraint else 1,
                original_index,
            )
            ranked.append((rank_key, result, is_priority))

        ranked.sort(key=lambda item: item[0])
        return [(result, is_priority) for _, result, is_priority in ranked]

    def _format_retrieved_result(self, index: int, result: dict[str, Any]) -> str | None:
        resource = result.get("resource")
        category = result.get("category")
        score = result.get("score", 0)

        label = getattr(category, "category_name", None) if category is not None else None
        category_content = (getattr(category, "content", None) or "").strip() if category is not None else ""
        resource_description = (
            (getattr(resource, "description", None) or "").strip()
            if resource is not None
            else ""
        )

        if category_content:
            content = f"fact: {category_content}"
            if resource_description and resource_description != category_content:
                content += f" | source_summary: {resource_description}"
        elif resource_description:
            content = resource_description
        else:
            return None

        prefix = f"{index}. "
        if label:
            prefix += f"[{label}] "
        return f"{prefix}{content} (score: {score:.2f})"

    def _is_high_constraint_memory(self, result: dict[str, Any]) -> bool:
        resource = result.get("resource")
        category = result.get("category")
        parts = [
            result.get("strategy", ""),
            getattr(category, "category_name", "") if category is not None else "",
            getattr(category, "content", "") if category is not None else "",
            getattr(resource, "description", "") if resource is not None else "",
            getattr(resource, "raw_content", "") if resource is not None else "",
        ]
        text = " ".join(str(part) for part in parts if part).lower()
        return any(term in text for term in HIGH_CONSTRAINT_MEMORY_TERMS)

    def _join_context(self, recent_context: str, retrieved_context: str) -> str:
        parts = [part for part in (recent_context, retrieved_context) if part]
        return "\n\n".join(parts)

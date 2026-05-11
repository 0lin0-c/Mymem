from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from services.constants import EPISODIC_MEMORY_CATEGORY
from tables import Category, Resource, ResourceCategory

CORE_SELF_CATEGORY = "Core Self"


@dataclass(frozen=True)
class CandidateCategoryProjection:
    row_index: int
    turn_index: int
    source_candidate_index: int
    view_type: str
    category_name: str | None
    content: str
    importance_score: int
    write_decision: str
    skip_reason: str = ""


@dataclass(frozen=True)
class CandidateViewWriteResult:
    row_index: int
    turn_index: int
    resource_id: str
    written_category_ids: list[str]
    projections: list[CandidateCategoryProjection]


class CandidateViewWritePolicy:
    def project_candidates(
        self,
        *,
        row_index: int,
        turn_index: int,
        candidates: list[dict[str, Any]],
    ) -> list[CandidateCategoryProjection]:
        return [
            self._project_candidate(
                row_index=row_index,
                turn_index=turn_index,
                source_candidate_index=index,
                candidate=candidate,
            )
            for index, candidate in enumerate(candidates)
        ]

    def _project_candidate(
        self,
        *,
        row_index: int,
        turn_index: int,
        source_candidate_index: int,
        candidate: dict[str, Any],
    ) -> CandidateCategoryProjection:
        view_type = str(candidate.get("view_type") or "")
        content = str(candidate.get("content") or "").strip()
        sensitivity = str(candidate.get("sensitivity") or "none")
        attribution_risk = str(candidate.get("attribution_risk") or "low")
        forget_conflict = bool(candidate.get("forget_conflict"))

        if not content:
            return self._skipped(row_index, turn_index, source_candidate_index, view_type, content, "empty_content")
        if sensitivity == "high":
            return self._skipped(row_index, turn_index, source_candidate_index, view_type, content, "high_sensitivity")
        if view_type != "constraint" and forget_conflict:
            return self._skipped(row_index, turn_index, source_candidate_index, view_type, content, "forget_conflict")
        if view_type == "task_event":
            return self._skipped(
                row_index,
                turn_index,
                source_candidate_index,
                view_type,
                content,
                "task_event_is_conversation_wrapper",
            )
        if view_type == "constraint":
            return self._skipped(
                row_index,
                turn_index,
                source_candidate_index,
                view_type,
                content,
                "constraint_is_policy_not_retrievable_memory",
            )
        if view_type == "advice_checklist":
            return self._skipped(
                row_index,
                turn_index,
                source_candidate_index,
                view_type,
                content,
                "assistant_advice_not_user_memory",
            )
        if view_type == "episodic_event" and attribution_risk == "high":
            return self._skipped(
                row_index,
                turn_index,
                source_candidate_index,
                view_type,
                content,
                "high_attribution_risk",
            )

        category_name = CORE_SELF_CATEGORY if view_type == "user_fact" else EPISODIC_MEMORY_CATEGORY
        return CandidateCategoryProjection(
            row_index=row_index,
            turn_index=turn_index,
            source_candidate_index=source_candidate_index,
            view_type=view_type,
            category_name=category_name,
            content=content,
            importance_score=2,
            write_decision="written",
        )

    def _skipped(
        self,
        row_index: int,
        turn_index: int,
        source_candidate_index: int,
        view_type: str,
        content: str,
        reason: str,
    ) -> CandidateCategoryProjection:
        return CandidateCategoryProjection(
            row_index=row_index,
            turn_index=turn_index,
            source_candidate_index=source_candidate_index,
            view_type=view_type,
            category_name=None,
            content=content,
            importance_score=0,
            write_decision="skipped",
            skip_reason=reason,
        )


class CandidateViewWriter:
    def __init__(
        self,
        *,
        session: Any,
        llm: Any,
        policy: CandidateViewWritePolicy | None = None,
    ) -> None:
        self.session = session
        self.llm = llm
        self.policy = policy or CandidateViewWritePolicy()

    async def write_turn(
        self,
        *,
        user_id: str,
        planned_turn: Any,
    ) -> CandidateViewWriteResult:
        projections = self.policy.project_candidates(
            row_index=planned_turn.row_index,
            turn_index=planned_turn.turn_index,
            candidates=planned_turn.candidates,
        )
        written_projections = [
            projection for projection in projections if projection.write_decision == "written"
        ]
        resource = await self._build_resource(user_id=user_id, planned_turn=planned_turn)
        self.session.add(resource)

        written_category_ids: list[str] = []
        for projection in written_projections:
            category = await self._build_category(user_id=user_id, projection=projection)
            self.session.add(category)
            self.session.add(
                ResourceCategory(
                    id=str(uuid.uuid4()),
                    resource_id=resource.id,
                    category_id=category.id,
                    relation_type="created",
                    note=f"candidate_view_projection:{projection.view_type}",
                )
            )
            written_category_ids.append(category.id)

        await self.session.flush()
        return CandidateViewWriteResult(
            row_index=planned_turn.row_index,
            turn_index=planned_turn.turn_index,
            resource_id=resource.id,
            written_category_ids=written_category_ids,
            projections=projections,
        )

    async def _build_resource(self, *, user_id: str, planned_turn: Any) -> Resource:
        raw_content = str(planned_turn.user_input or "")
        assistant_response = str(planned_turn.assistant_response or "")
        description = (
            "candidate projection source: "
            f"user={raw_content}"
            + (f" assistant={assistant_response}" if assistant_response else "")
        )
        return Resource(
            id=str(uuid.uuid4()),
            user_id=user_id,
            modality="text",
            raw_content=raw_content,
            assistant_response=assistant_response,
            description=description,
            description_vector=await self.llm.get_embedding(description),
            importance_score=2,
        )

    async def _build_category(
        self,
        *,
        user_id: str,
        projection: CandidateCategoryProjection,
    ) -> Category:
        if projection.category_name is None:
            raise ValueError("Cannot write a projection without category_name")
        return Category(
            id=str(uuid.uuid4()),
            user_id=user_id,
            category_name=projection.category_name,
            content=projection.content,
            content_vector=await self.llm.get_embedding(projection.content),
            importance_score=projection.importance_score,
        )

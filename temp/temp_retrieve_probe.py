import asyncio
import json
from core.database import AsyncSessionLocal
from repositories import UserRepository
from services.llm.factory import LLMFactory
from services.retrieval.retriever import MemoryRetriever

TARGET = "What did Caroline research?"

async def main():
    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_username("Caroline")
        llm = LLMFactory.get_provider()
        retriever = MemoryRetriever(session, llm)
        results = await retriever.retrieve(str(user.id), TARGET, top_k=15)
        previews = []
        for item in results[:8]:
            resource = item.get("resource")
            category = item.get("category")
            text = resource.description if resource is not None else category.content if category is not None else ""
            previews.append({
                "score": round(item.get("score", 0.0), 4),
                "strategy": item.get("strategy"),
                "text": text[:180],
            })
        print(json.dumps(previews, ensure_ascii=False, indent=2))

asyncio.run(main())

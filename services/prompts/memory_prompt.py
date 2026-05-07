# Memory Extraction Prompts

MEMORY_EXTRACTION_PROMPT = """# Role
You are the core memory routing engine for an AI Agent. Your tasks are:
1. Generate a comprehensive summary of the user input and AI response
2. Extract multiple atomic information items from the summary and categorize them

# System Context
Current system time: {current_time}
Use this timestamp to precisely calculate any relative time expressions in the user's input (e.g., "tomorrow", "just now", "next week").

# Taxonomy (Categories)
You must categorize each atomic information item into exactly one of the categories listed below:
{category_details}

# Importance Score Criteria (0-3)

3 - Core foundation: health status, allergies, core values, lifelong goals, major long-term preferences, important relationships

2 - High-value memory: major projects, milestone events, important decisions, reusable knowledge, deep insights, medium-term plans

1 - Daily context: ordinary activities, recent experiences, short-term plans, temporary contextual information

0 - Noise or low-value content: pure pleasantries, emotional venting without new facts, invalid text, or content not worth retrieving later

# Output Language (Critical)
- **ALWAYS** use the same language as the user's input for memory content (summary, response_summary, atomic_items content).
- Determine the output language only from the actual text under `[User Input]`; ignore labels, taxonomy text, tool/schema descriptions, timestamps, and system instructions when deciding the language.
- If the user speaks Chinese, output memory content in Chinese.
- If the user speaks English, output memory content in English.
- If the user mixes languages, output in the dominant language of the conversation.
- Do not output Chinese memory content when `[User Input]` is English.
- **Preserve names, technical terms, quoted phrases, and domain-specific expressions in their original language.** Do not translate technical terms (e.g., "Docker", "Python", "API") or proper nouns.
- **Category names must be copied EXACTLY from the Taxonomy list above. Do NOT translate category names.**

# Workflow & Output Constraints

## Task Description
1. **Summary**: Integrate the user input and AI response into a fact-preserving third-person description. The summary MUST retain all specific nouns, medical terms, activity names, named entities, and preference objects verbatim — do NOT abstract them into broader categories (e.g., keep "appendectomy" not "surgery", keep "coloring books" not "art materials", keep "swinging at the playground" not "outdoor activity").
2. **Overall Score**: Rate the importance of the comprehensive summary (importance_score, 0-3)
3. **AI Response Summary**: If the AI has a response, generate a summary of the response (response_summary)
4. **Atomic Extraction**: Extract multiple independent atomic information items from the conversation, each:
   - Must belong to one of the categories listed in the Taxonomy section
   - Must have an independent importance score
   - Must be independent and self-contained information units
   - Must use the same language as the user's input

## Source and Attribution Rules
- Store only facts directly stated, implied by, or explicitly confirmed by the user in `[User Input]`.
- Do not attribute the assistant's actions, preferences, family, belongings, or experiences to the user.
- If `[AI Response]` contains advice, options, or checklist steps that the user asked for, store the advice as `advice_checklist` with the user as the requester, not as something the user already did.
- Keep speaker direction clear: "the user asked about X" is different from "the user did X".
- When another person is mentioned, preserve who did what. Do not merge another person's event into the user's own profile.
- Do not invent facts, dates, places, ownership, family relationships, or motivations that are not supported by the user input.

## Quoted Content Audit (CRITICAL)
When the user asks you to refine, translate, polish, or improve a piece of text, that text is NOT just a task artifact — it often contains real personal facts, preferences, conditions, and experiences about the user.
- **Do NOT treat the user's original text as mere task context.** Scan it for personal facts the same way you would scan a direct statement.
- If the user says "help me refine this email" and the email body says "I take my animal coloring pages to calm down", extract "The user uses animal coloring pages to calm down" as a preference — do NOT just store "The user asked for help refining an email."
- If the user asks to translate "I enjoy picking apples at the orchard every fall", extract "The user enjoys picking apples in the fall" — do NOT just store "The user requested a translation."
- If the user shares a passage about their own life for polishing/translation (e.g., a diary entry, a personal letter, a self-introduction), the content of that passage is autobiographical evidence — extract facts from it.
- The rule: **extract facts from WHAT the user wrote/shared, not just from the fact THAT they asked for help.** Both the task and the content facts should be extracted.

## Narrative Attribution Rule
Third-person stories are weaker evidence than direct first-person statements.
- Do NOT convert a third-person character's stable traits, values, preferences, or medical conditions into Core Self facts unless the user explicitly says the passage is autobiographical or about them.
- If a third-person passage describes a concrete personal-sounding event, extract it only as a low-confidence Episodic Memory with a qualifier, e.g. "The user described an experience of [X], shared through a narrative about [character name]."
- Do NOT infer values or personality traits from how a story resolves. A story about creative problem solving is not evidence that the user values creativity unless the user states that directly.
- Example: the user shares "Lena was walking home from the park… she saw police officers rushing past" for refinement → extract "The user described witnessing a police incident through a narrative about Lena" with `extraction_origin="third_person_narrative"`.
- Example: the user shares "Daniel Harper: I've been avoiding the playground since a kid got hurt" for polishing → extract an Episodic Memory about a described playground injury narrative, not a Core Self fact that the user avoids playgrounds.
- Clearly fictional scenarios (e.g., "Once upon a time in a faraway kingdom") are excluded.
- If uncertain, either skip the item or extract only the qualified low-confidence episodic description.

## Forget/Negation Survival Rule
When the user asks to forget a preference or fact, the forget/negation itself must be stored. However, the UNDERLYING INTENT or NEED that prompted the original preference often still exists and must also be stored separately.
- If the user first asks about "fun creative activities for kids" and then says "forget that I like pottery workshops", the need for "fun creative activities for kids" STILL EXISTS — store it as a separate positive fact.
- If the user first discusses "tips for intense physical activity" and then says "forget my asthma preference", the need for "tips for intense physical activity" STILL EXISTS — store it separately.
- If the AI provided useful general advice before the forget request (e.g., pacing strategies, alternative activity ideas), that advice is still valid and should be stored as `advice_checklist`.
- The forget instruction only removes the SPECIFIC preference — it does not erase the user's broader need or the general advice that was given.

## Summary Fidelity Rules
- The `summary` is the primary retrieval key — it gets embedded as a vector. If key terms are abstracted away, they can NEVER be found by vector search.
- **Preserve specific nouns verbatim**: medical conditions (appendectomy, concussion, asthma, lactose intolerance), activity names (swinging, pottery workshops, apple picking, coloring books), object names (cardboard cut-outs, blanket forts, hot dogs), and named entities.
- **Do NOT generalize into broader categories**: "appendectomy" → "surgery" ❌, "coloring books" → "art materials" ❌, "swinging at the playground" → "outdoor activity" ❌
- **Include preference polarity**: if the user likes, enjoys, prefers, avoids, has, or had something, keep the exact preference statement in the summary.
- **Include specific details that differentiate**: "minor car accident" vs "car accident", "kids pottery workshops" vs "pottery workshops", "backyard camping" vs "camping".

## Preference & Fact Extraction Rules
- **Every explicit preference, condition, or behavioral fact stated by the user MUST be extracted as a standalone atomic item**, not buried inside a conversation summary.
- Good: atomic item content = "The user enjoys coloring in coloring books"
- Bad: atomic item content = "The user discussed creative activities" (preference lost)
- Good: atomic item content = "The user had an appendectomy at age 6"
- Bad: atomic item content = "The user asked about health precautions" (fact never stored)
- **Preserve the user's exact wording for key terms**: if the user says "I like swinging at the playground", the atomic item should say "enjoys swinging at the playground", NOT "enjoys outdoor activities".
- **Self-contained retrieval**: each atomic item must contain enough specific terms to be found by a future query. An item like "The user enjoys outdoor activities" will never match a query about "swinging" or "playground".

## Memory Type Rules
Choose one `memory_type` for each atomic item:
- `profile_fact`: stable identity, preference, value, health, long-term goal, or durable personal trait.
- `event_fact`: concrete past or planned activity, experience, attendance, research, creation, visit, observation, or decision.
- `exact_fact`: a directly answerable specific fact such as yes/no, ownership, who/what/where/when/how many, negation, or a named object relation.
- `symbolic_meaning`: what a drawing, object, phrase, symbol, or image means, represents, or stands for.
- `advice_checklist`: advice, steps, recommendations, constraints, or checklist items given in response to the user's request.
- `relationship_fact`: relationship, social connection, family/friend/colleague information, or interpersonal dynamic.
- `media_fact`: facts about a photo, image, drawing, document, audio, video, object appearance, or media content.
- `knowledge_fact`: reusable domain knowledge, study note, insight, concept, or asset that is not mainly a personal episode.

Use `fact_type` for a more specific label when helpful, such as `who_did_what`, `time`, `location`, `yes_no`, `negation`, `ownership`, `event_topic`, `object_relation`, `symbol_meaning`, `checklist`, or `preference`.

## Evidence Origin Rules
Set `extraction_origin` for every atomic item. This metadata is used only during write-time filtering and importance adjustment.
- `direct_user_statement`: the user directly states or confirms the fact.
- `quoted_first_person`: the fact comes from first-person text the user provided for refinement, translation, or polishing.
- `third_person_narrative`: the fact comes from a third-person story or named character passage.
- `assistant_advice`: the item stores advice/options/checklist steps from the assistant response requested by the user.
- `surviving_need`: a broader user need that remains after a specific preference/fact is forgotten.
- `forget_instruction`: the user explicitly asks to forget or stop using a specific fact/preference.

Confidence guidance:
- Use 0.85-1.0 for direct user statements and clearly autobiographical first-person quoted content.
- Use 0.55-0.75 for indirect but supported first-person quoted content.
- Use 0.45-0.60 for third-person narrative items, and keep them qualified.
- Use below 0.45 for uncertain or speculative items; those should usually be omitted.

## Episodic Memory Extraction Rules
- Use **Episodic Memory** for concrete situated facts from the user's message: what the user did, researched, attended, saw, made, planned, where it happened, who was involved, or what an object/symbol meant in that situation.
- For Episodic Memory items, write a normalized factual sentence that is specific and answerable. Do not collapse it into a broad preference or vague life summary.
- Preserve concrete activity themes, checklist-like facts, object descriptions, symbolic meanings, and named entities when they appear in the user input.
- Do not include raw quotes in the atomic item. The source message is linked separately by the storage layer through ResourceCategory -> Resource.raw_content.
- Use the system timestamp only to resolve relative time expressions; do not invent an event date when the user did not state one.
- If the user gives relative time text, preserve it in `time_text`. The database conversation time is stored separately by the write path; do not fabricate `happened_at`.

## Content Fidelity Rules
- `content` is the Category fact index. It should be a concise normalized fact sentence, not a raw transcript.
- For exact facts, keep all answer-bearing details: who, what, when, where, yes/no, negation, object description, symbol meaning, event topic, checklist step, and speaker ownership.
- Prefer several precise atomic items over one broad summary when a message contains multiple answerable facts.
- Avoid vague memories like "the user discussed adoption" when the source supports a sharper fact like "The user researched adoption agencies."
- Do not include unsupported emotion or motive unless the user explicitly says it.
- **CRITICAL: Preserve specific terms for retrieval**. The `content` field gets vector-embedded. If you abstract away key nouns, the item becomes unretrievable.
  - "Had an appendectomy at age 6" ✅ — "Had surgery as a child" ❌
  - "Enjoys coloring in coloring books" ✅ — "Enjoys creative activities" ❌
  - "Attends workshops on pottery for kids" ✅ — "Attends art workshops" ❌
  - "Has mild lactose intolerance" ✅ — "Has dietary restrictions" ❌
  - "Uses prescription glasses for nearsightedness" ✅ — "Has vision issues" ❌

## Output Format
Output strictly in the following JSON structure without any Markdown formatting:

{{
  "summary": "<Fact-preserving third-person summary retaining specific nouns, medical terms, activity names, named entities, and preference objects verbatim>",
  "importance_score": <Overall importance score for the summary, 0-3>,
  "response_summary": "<Core points summary of AI response, empty string if no response>",
  "atomic_items": [
    {{
      "category_name": "<Category name, copied exactly from the Taxonomy list>",
      "content": "<Atomic memory content, one independent piece of information>",
      "importance_score": <Importance score for this item, 0-3>,
      "memory_type": "<profile_fact | event_fact | exact_fact | symbolic_meaning | advice_checklist | relationship_fact | media_fact | knowledge_fact>",
      "fact_type": "<Optional specific fact label>",
      "subject": "<Who or what the memory is about, usually the user or a named person/object>",
      "source_role": "user",
      "time_text": "<Original time expression from the user input, or empty string>",
      "confidence": <Confidence score from 0.0 to 1.0>,
      "extraction_origin": "<direct_user_statement | quoted_first_person | third_person_narrative | assistant_advice | surviving_need | forget_instruction>"
    }},
    {{
      "category_name": "<Category name, copied exactly from the Taxonomy list>",
      "content": "<Another atomic content>",
      "importance_score": <Score>,
      "memory_type": "<Memory type>",
      "fact_type": "<Optional specific fact label>",
      "subject": "<Subject>",
      "source_role": "user",
      "time_text": "",
      "confidence": <Confidence score from 0.0 to 1.0>,
      "extraction_origin": "<Extraction origin>"
    }}
  ]
}}

## Notes
- The atomic_items array can be empty if the conversation is noise
- Each atomic item should be independent and self-contained
- A single conversation may produce multiple atomic items belonging to the same category
- Ensure each atomic item's importance_score reasonably reflects its value
- The extra atomic item metadata is for traceability and evaluation. The storage layer persists `content` as Category.content and links it to the original Resource; do not put source quotes inside `content`.
"""


CATEGORY_MEMORY_EXTRACTION_PROMPT = """# Role
You are the dedicated memory extraction engine for one target memory category.
Your task is to extract only atomic memory items that belong to the target category.

# System Context
Current system time: {current_time}
Use this timestamp to precisely calculate any relative time expressions in the user's input (e.g., "tomorrow", "just now", "next week").

# Target Category
[{category_name}]: {category_description}

# Category-Specific Extraction Requirements
{category_requirements}

# Importance Score Criteria (0-3)
3 - Core foundation: health status, allergies, core values, lifelong goals, major long-term preferences, important relationships
2 - High-value memory: major projects, milestone events, important decisions, reusable knowledge, deep insights, medium-term plans
1 - Daily context: ordinary activities, recent experiences, short-term plans, temporary contextual information
0 - Noise or low-value content: pure pleasantries, emotional venting without new facts, invalid text, or content not worth retrieving later

# Output Language (Critical)
- Use the same language as `[User Input]` for memory content; ignore taxonomy labels and system text when deciding language.
- Preserve names, technical terms, quoted phrases, and domain-specific expressions in their original language.
- **Every atomic item must use category_name exactly as `{category_name}`. Do NOT translate or rename the category.**

# Source and Attribution Rules
- Store only facts directly stated, implied by, or explicitly confirmed by the user in `[User Input]`.
- Do not attribute the assistant's actions, preferences, family, belongings, or experiences to the user.
- If `[AI Response]` contains advice, options, or checklist steps that the user asked for and the advice belongs to the target category, store the advice as `advice_checklist` with the user as the requester.
- Keep speaker direction clear: "the user asked about X" is different from "the user did X".
- When another person is mentioned, preserve who did what. Do not merge another person's event into the user's own profile.
- Do not invent facts, dates, places, ownership, family relationships, or motivations that are not supported by the user input.

# Quoted Content Audit (CRITICAL)
When the user asks you to refine, translate, polish, or improve a piece of text, that text is NOT just a task artifact — it often contains real personal facts, preferences, conditions, and experiences about the user.
- Do NOT treat the user's original text as mere task context. Scan it for personal facts the same way you would scan a direct statement.
- If the user says "help me refine this email" and the email body says "I use my coloring pages to calm down", extract "The user uses coloring pages to calm down" as a preference — do NOT just store "The user asked for help refining an email."
- If the user asks to translate a passage about visiting an orchard, extract "The user enjoys visiting an orchard/picking apples" — do NOT just store "The user requested a translation."
- The rule: extract facts from WHAT the user wrote/shared, not just from the fact THAT they asked for help.

# Narrative Attribution Rule
- Third-person stories are weaker evidence than direct first-person statements.
- Do NOT convert a third-person character's stable traits, values, preferences, or medical conditions into Core Self facts unless the user explicitly says the passage is autobiographical or about them.
- If a third-person passage describes a concrete personal-sounding event, extract it only as a low-confidence Episodic Memory with a qualifier.
- Do NOT infer values or personality traits from how a story resolves.
- Clearly fictional scenarios (e.g., "Once upon a time in a faraway kingdom") are excluded.
- If uncertain, either skip the item or extract only the qualified low-confidence episodic description with `extraction_origin="third_person_narrative"`.

# Forget/Negation Survival Rule
When the user asks to forget a preference or fact, the forget/negation itself must be stored. However, the UNDERLYING INTENT or NEED that prompted the original preference often still exists and must also be stored separately.
- If the user first asks about "fun creative activities for kids" and then says "forget that I like pottery workshops", the need for "fun creative activities for kids" STILL EXISTS — store it as a separate positive fact.
- If the AI provided useful general advice before the forget request (e.g., pacing strategies, alternative activity ideas), that advice is still valid and should be stored as `advice_checklist`.
- The forget instruction only removes the SPECIFIC preference — it does not erase the user's broader need or the general advice that was given.

# Summary Fidelity Rules
- The `summary` is a retrieval key that gets embedded as a vector. If key terms are abstracted away, they can NEVER be found by vector search.
- **Preserve specific nouns verbatim**: medical conditions, activity names, object names, named entities, and preference objects.
- **Do NOT generalize**: "appendectomy" → "surgery" ❌, "coloring books" → "art materials" ❌, "swinging at the playground" → "outdoor activity" ❌
- **Include preference polarity** in the summary: likes, enjoys, prefers, avoids, has, had.
- **Include differentiating details**: "minor car accident" vs "car accident", "kids pottery workshops" vs "pottery workshops".

# Preference & Fact Extraction Rules
- **Every explicit preference, condition, or behavioral fact stated by the user MUST be extracted as a standalone atomic item for this category**, not buried inside a broad summary.
- Good: "The user enjoys coloring in coloring books" ✅
- Bad: "The user discussed creative activities" ❌ (preference lost)
- Good: "The user had an appendectomy at age 6" ✅
- Bad: "The user asked about health precautions" ❌ (fact never stored)
- **Preserve the user's exact wording for key terms** so the item can be retrieved by future queries containing those terms.

# Memory Type Rules
Choose one `memory_type` for each atomic item:
- `profile_fact`: stable identity, preference, value, health, long-term goal, or durable personal trait.
- `event_fact`: concrete past or planned activity, experience, attendance, research, creation, visit, observation, or decision.
- `exact_fact`: a directly answerable specific fact such as yes/no, ownership, who/what/where/when/how many, negation, or a named object relation.
- `symbolic_meaning`: what a drawing, object, phrase, symbol, or image means, represents, or stands for.
- `advice_checklist`: advice, steps, recommendations, constraints, or checklist items given in response to the user's request.
- `relationship_fact`: relationship, social connection, family/friend/colleague information, or interpersonal dynamic.
- `media_fact`: facts about a photo, image, drawing, document, audio, video, object appearance, or media content.
- `knowledge_fact`: reusable domain knowledge, study note, insight, concept, or asset that is not mainly a personal episode.

Use `fact_type` for a more specific label when helpful, such as `who_did_what`, `time`, `location`, `yes_no`, `negation`, `ownership`, `event_topic`, `object_relation`, `symbol_meaning`, `checklist`, or `preference`.

# Evidence Origin Rules
Set `extraction_origin` for every atomic item. It is used only during write-time filtering and importance adjustment.
- `direct_user_statement`: the user directly states or confirms the fact.
- `quoted_first_person`: the fact comes from first-person text the user provided for refinement, translation, or polishing.
- `third_person_narrative`: the fact comes from a third-person story or named character passage.
- `assistant_advice`: the item stores advice/options/checklist steps from the assistant response requested by the user.
- `surviving_need`: a broader user need that remains after a specific preference/fact is forgotten.
- `forget_instruction`: the user explicitly asks to forget or stop using a specific fact/preference.
- Use confidence below 0.45 for uncertain or speculative items; those should usually be omitted.

# Category vs Memory Type Rules
- `category_name` is the storage bucket and must be exactly `{category_name}` in this single-category extraction call.
- `memory_type` is a secondary diagnostic label inside that bucket. It may refine the fact type but must not override the target category.
- If a fact fits the `memory_type` label but does not belong to `{category_name}`, do not extract it in this call.
- Example: an `event_fact` belongs in Episodic Memory, not Core Self; a `profile_fact` belongs in Core Self, not Episodic Memory.

# Category Conflict Rules
- If one fact could fit multiple categories, extract it only when `{category_name}` is the best primary category.
- Use Core Self for durable traits, preferences, health, identity, values, and long-term goals.
- Use Episodic Memory for concrete situated events, plans, actions, requests, visits, attendance, creations, observations, and updates.
- Use Knowledge Base for reusable knowledge, project assets, documents, technical facts, study notes, and reusable instructions.
- Use Social Graph for people, relationships, groups, social roles, and interpersonal interactions.
- For dynamic categories, use the target category description as the primary routing rule, but still reject facts that clearly belong to one of the four fixed categories.

# Content Fidelity Rules
- Extract facts for the target category directly from the original `[User Input]` and relevant `[AI Response]`; do not rely on a broad paraphrase when answer-bearing details are present.
- Keep all answer-bearing details: who, what, when, where, yes/no, negation, object description, symbolic meaning, event topic, checklist step, preference object, and speaker ownership.
- Preserve concrete objects, locations, activity names, named entities, file/path types, relationship names, sensitive information types, and update/forget/negation signals.
- Prefer several precise atomic items over one broad summary when the message contains multiple answerable facts.
- Avoid vague memories like "the user discussed outdoor activities" when the source supports a sharper fact like "The user asked for low-cost outdoor activities with friends that require little equipment."
- **CRITICAL: Preserve specific terms for retrieval**. The `content` field gets vector-embedded. If you abstract away key nouns, the item becomes unretrievable.
  - "Had an appendectomy at age 6" ✅ — "Had surgery as a child" ❌
  - "Enjoys coloring in coloring books" ✅ — "Enjoys creative activities" ❌
  - "Attends workshops on pottery for kids" ✅ — "Attends art workshops" ❌
  - "Has mild lactose intolerance" ✅ — "Has dietary restrictions" ❌
- `summary` may briefly summarize the target-category evidence, but it must not replace precise `atomic_items`.
- If there are no facts for the target category, return an empty `atomic_items` array.

# Review & Validate Before Output
- Remove items that belong to a different category.
- Merge semantically duplicate items within this category, keeping the most specific wording.
- Resolve direct contradictions by keeping the latest or most explicit user-stated information.
- Reject vague items when the source supports a more concrete item.
- Reject items based only on assistant speculation or follow-up questions.

# Output Format
Output strictly in the following JSON structure without any Markdown formatting:

{{
  "summary": "<Brief target-category summary, or empty string if no target-category content>",
  "importance_score": <Overall importance score for this category extraction, 0-3>,
  "response_summary": "<Core points summary of AI response related to this category, empty string if none>",
  "atomic_items": [
    {{
      "category_name": "{category_name}",
      "content": "<Atomic memory content, one independent piece of information>",
      "importance_score": <Importance score for this item, 0-3>,
      "memory_type": "<profile_fact | event_fact | exact_fact | symbolic_meaning | advice_checklist | relationship_fact | media_fact | knowledge_fact>",
      "fact_type": "<Optional specific fact label>",
      "subject": "<Who or what the memory is about, usually the user or a named person/object>",
      "source_role": "user",
      "time_text": "<Original time expression from the user input, or empty string>",
      "confidence": <Confidence score from 0.0 to 1.0>,
      "extraction_origin": "<direct_user_statement | quoted_first_person | third_person_narrative | assistant_advice | surviving_need | forget_instruction>"
    }}
  ]
}}
"""


CORE_SELF_EXTRACTION_REQUIREMENTS = """Extract only stable user profile information:
- Identity, age/life stage, role, long-term preferences, habits, values, goals, health conditions, allergies, durable constraints, and durable dislikes.
- Preserve the exact preference object and polarity: likes, dislikes, prefers, avoids, no longer likes, wants forgotten, changed preference, or contradicted prior preference.
- Preserve specific terms verbatim: do NOT abstract "appendectomy" into "surgery", "lactose intolerance" into "dietary issues", "nearsightedness" into "vision problems", or "coloring books" into "art activities". The exact terms are critical for future retrieval.
- Each distinct preference, condition, or trait MUST be a separate atomic item. Do not merge "enjoys swinging at the playground" and "likes hot dogs at cookouts" into a single vague "likes outdoor activities and food".
- Preserve sensitive information as a safe type-level fact when appropriate, such as "the user shared a physical address" or "the user shared a credit card number"; do not invent or expose unsupported details.
- **Quoted Content**: If the user shares first-person text for refinement/translation that reveals a personal preference, health condition, or trait, extract it as if the user had stated it directly and set `extraction_origin="quoted_first_person"`.
- **Narrative Attribution**: Do NOT extract stable traits, values, preferences, or conditions from third-person narratives into Core Self unless the user explicitly says the narrative is autobiographical or about them.
- **Direct Values Only**: Do NOT infer values/personality traits from a story's plot or resolution. Store values only when the user directly states them.
- **Forget Survival**: When the user says "forget that I prefer X", store the forget instruction with `extraction_origin="forget_instruction"`, BUT if there is an underlying need that remains, extract that surviving need separately with `extraction_origin="surviving_need"`.

Forbidden:
- Event-related items are forbidden unless the event explicitly establishes a durable identity, habit, preference, or condition.
- Temporary plans, one-off requests, errands, visits, attendance, projects, and advice checklists are forbidden.
- Facts learned only from the assistant's follow-up question or unsupported inference are forbidden.

Good examples:
- The user prefers watercolor painting over drawing superheroes.
- The user has prescription glasses for nearsightedness.
- The user no longer wants pottery workshops for kids remembered as a preference.
- The user has mild lactose intolerance managed with dietary adjustments.
- The user enjoys coloring in coloring books.
- The user is interested in fun creative activities for children (surviving need after forgetting pottery preference).

Bad examples:
- The user went to a community center on a hot afternoon. (Episodic Memory, not Core Self)
- The user asked for ideas for a block party. (Episodic Memory request, not a durable trait)
- The user may enjoy art because the assistant suggested art activities. (Unsupported inference)
- The user has dietary restrictions. (Too vague — specify "lactose intolerance")
- The user enjoys creative activities. (Too vague — specify "coloring in coloring books")"""


EPISODIC_MEMORY_EXTRACTION_REQUIREMENTS = """Extract only concrete situated memories:
- Past, current, or planned activities, experiences, attendance, research, creation, visits, observations, requests, and decisions.
- Preserve who/what/where/when, concrete objects, activity names, scene details, materials, tools, locations, and exact actions.
- Do not collapse a concrete episode into a broad preference. For example, keep "the user attended a kids pottery workshop" instead of "the user likes art."
- Preserve update, negation, and forget signals as concrete events when the user explicitly asks to forget or changes earlier information.
- Preserve specific terms verbatim: do NOT abstract "car accident" into "incident", "burglary while family was asleep" into "safety concern", or "police chase near the park" into "distressing event". Exact terms are critical for retrieval.
- **Quoted Content**: If the user shares first-person text for refinement/translation that describes a concrete personal experience, extract that experience as an episodic fact with `extraction_origin="quoted_first_person"`.
- **Narrative Attribution**: If the user shares a third-person narrative that describes a concrete personal-sounding experience, extract only a qualified low-confidence episodic fact with `extraction_origin="third_person_narrative"`. Do not turn it into an unqualified user profile fact.
- **Forget Survival**: When the user asks to forget a specific activity, store the forget event with `extraction_origin="forget_instruction"`, BUT also extract the surviving intent/request separately with `extraction_origin="surviving_need"`. E.g., user asked about "creative kids activities", then said "forget pottery" → store the forget AND store "The user is looking for creative activities for children (excluding pottery)."

Forbidden:
- Behavioral patterns, habits, durable preferences, identity traits, health conditions, and long-term goals are forbidden.
- Reusable domain knowledge, study facts, technical concepts, and general advice detached from a concrete user request are forbidden.
- Relationship facts are forbidden unless the concrete interaction/event is the main memory.

Good examples:
- The user asked for low-cost outdoor activities with friends that require little equipment.
- The user planned a surprise block party at a home address in Bloomington, Minnesota.
- The user asked to forget that they attend workshops on pottery for kids.
- The user witnessed a severe car accident involving a neighbor while riding in the family car.
- The user experienced a burglary at their home at night while the family was asleep.
- The user is looking for fun creative activities for a group of children (surviving request after forgetting pottery preference).

Bad examples:
- The user likes outdoor activities. (Core Self preference, too broad)
- The user knows Python syntax. (Knowledge Base, not an event)
- The user went on a hike. (Too vague if time/place/people/details are available)
- The user had a distressing experience. (Too vague — specify what happened)"""


KNOWLEDGE_BASE_EXTRACTION_REQUIREMENTS = """Extract only reusable knowledge and assets:
- Study notes, project assets, technical facts, file or path references, tool names, concepts, reusable checklists, and domain knowledge the user wants available later.
- Preserve named entities, project names, technology names, file/path types, command/tool names, conceptual relationships, and exact reusable constraints.
- Preserve specific terms verbatim: do NOT abstract "DataHandler.py" into "a project file", "Science Club" into "a school club", or "Git-style collaboration" into "version control".
- For sensitive technical or identity data, preserve the information type and safe handling requirement rather than expanding it unnecessarily.

Forbidden:
- User-specific traits, preferences, opinions, habits, health conditions, or identity facts are forbidden.
- One-time events, attendance, visits, requests, and personal experiences are forbidden unless the reusable asset/knowledge itself is the main memory.
- Personal relationships and social roles are forbidden unless they define access or ownership of a reusable asset.

Good examples:
- The user's Science Club project has a data handler file path under `/home/oliver.jensen/SchoolProjects/ScienceClub/DataHandler.py`.
- The user asked for version control and secure file management strategies for a school club project.
- The project uses Git-style collaboration as a reusable file management strategy.

Bad examples:
- The user is interested in learning basic sign language. (Core Self preference/interest)
- The user worked on a science project today. (Episodic Memory event)
- The user likes programming. (Core Self preference, not reusable knowledge)"""


SOCIAL_GRAPH_EXTRACTION_REQUIREMENTS = """Extract only interpersonal and relationship information:
- Family, friends, classmates, coworkers, neighbors, teams, communities, and named people or groups connected to the user.
- Preserve names, relationship direction, roles, group membership, interpersonal preferences, shared activities, and concrete interactions.
- Preserve specific terms verbatim: do NOT abstract "grandmother" into "family member", "Science Club team" into "a group", or "neighbors in Bloomington" into "community".
- Keep who did what clear: another person's trait or action must not become the user's own trait.

Forbidden:
- Generic social advice is forbidden unless it refers to a specific relationship, person, group, or social context involving the user.
- Solitary user preferences, health facts, technical assets, and generic events without a social relation are forbidden.
- Another person's action must not be stored as the user's trait.

Good examples:
- The user wants to do nature-inspired indoor activities with their grandmother on a rainy afternoon.
- The user is planning an event for neighbors in Bloomington, Minnesota.
- The user collaborates with a school Science Club team.

Bad examples:
- The user enjoys gardening. (Core Self unless tied to a specific relationship)
- The user asked for community center activities. (Episodic Memory request, not a relationship)
- The user's grandmother likes drawing. (Only store if explicitly stated and relevant to the relationship)"""


GENERIC_CATEGORY_EXTRACTION_REQUIREMENTS = """Extract only facts that clearly belong to the target category description:
- Use the target category name and description as the routing rule.
- Preserve answer-bearing details and avoid broad paraphrases.
- Preserve specific terms verbatim: do NOT abstract medical conditions, activity names, object names, named entities, or preference objects into broader categories.
- If the category is user-specific or dynamic, keep facts specific enough to be retrieved later for that user's personalized questions.
- Every explicit preference, condition, or behavioral fact MUST be a standalone atomic item with verbatim key terms.
- **Quoted Content**: If the user shares first-person text for refinement/translation that contains facts relevant to this category, extract those facts from the CONTENT of the text and set `extraction_origin="quoted_first_person"`.
- **Narrative Attribution**: If the user shares a narrative using a third-person name, extract only qualified low-confidence concrete events when relevant; do not infer stable preferences, values, or conditions unless autobiographical attribution is explicit.
- **Forget Survival**: When the user asks to forget a specific fact, also extract any surviving broader need or request that remains relevant to this category with `extraction_origin="surviving_need"`.

Conflict handling:
- Do not extract facts that clearly belong to Core Self, Episodic Memory, Knowledge Base, or Social Graph unless the dynamic category description is a more specific subdomain of that fact.
- If the source fact has no clear connection to the target category description, return no item.
- If two candidate items overlap, keep the more specific one.

Good example:
- For a dynamic category named "Therapeutic Journey", extract a specific therapy-related background or coping context stated by the user.

Bad examples:
- Extracting every emotional sentence just because the category is broad. (Too vague)
- Extracting a family relationship into a dynamic category when Social Graph is the clearer category.
- Extracting a one-time activity into a dynamic category when Episodic Memory is the clearer category."""

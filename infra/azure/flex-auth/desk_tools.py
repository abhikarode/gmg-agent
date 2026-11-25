"""Call the existing GMG services from Flex when a tool is used."""

from functools import lru_cache
from typing import TYPE_CHECKING

from azure.core.exceptions import AzureError
from markdown_it import MarkdownIt

from expertise import CATALOG, MAX_TOPICS, expertise_entries, load_topics, save_topics, validate_topics
from hosted_inference import inference_status
from member_desk import published_snapshot, published_version
from membership import expertise_key

if TYPE_CHECKING:
    from people_match import MatchResponse

markdown = MarkdownIt("commonmark", {"html": False}).disable("image")
PEOPLE_MODEL_READ_SECONDS = 5


@lru_cache(maxsize=1)
def _data(version: str):
    from ai_agent import DataStore

    return DataStore(snapshot=published_snapshot(version))


@lru_cache(maxsize=1)
def _directory_view(version: str, topics: tuple):
    from ai_agent import DataStore

    base = _data(version)
    if not topics:
        return base
    by_key = dict(topics)
    return DataStore(snapshot={"jobs": base.get_jobs(), "users": [
        {**user, "_gmg_member_expertise": by_key.get(expertise_key(str(user.get("unique_profile_id") or "")), ())}
        for user in base.get_users()
    ]})


@lru_cache(maxsize=1)
def _agent(version: str, topics: tuple):
    from ai_agent import AIAgent

    return AIAgent(data_store=_directory_view(version, topics))


@lru_cache(maxsize=1)
def _people_index(version: str, topics: tuple):
    from people_match import PeopleIndex

    return PeopleIndex(_directory_view(version, topics).get_users())


def _directory_topics() -> tuple:
    try:
        return expertise_entries()
    except (AzureError, OSError, ValueError, TypeError, KeyError):
        return ()


def find_people(need: str, place: str) -> tuple["MatchResponse", str]:
    from people_match import recommend

    version, topics = published_version(), _directory_topics()
    index = _people_index(version, topics)
    agent = _agent(version, topics)

    def complete(instructions: str, payload: str, schema: dict, timeout: float) -> str:
        return agent.complete_people_match(instructions, payload, schema, min(timeout, PEOPLE_MODEL_READ_SECONDS))

    state = inference_status.set("directory")
    try:
        result = recommend(index, need, place, agent.model, complete,
                           rank_payload_limit=2200 if agent.hosted else None, fallback_on_plan_failure=True)
        return result, inference_status.get()
    finally:
        inference_status.reset(state)


def ask_gmg(question: str) -> tuple[str, str]:
    from ai_agent import ModelUnavailable

    state = inference_status.set("directory")
    try:
        answer = _agent(published_version(), _directory_topics()).chat(question)
    except ModelUnavailable:
        return "", inference_status.get()
    else:
        return markdown.render(answer), inference_status.get()
    finally:
        inference_status.reset(state)


def opportunities(query: str) -> str:
    from ai_agent import AIAgent

    jobs = _data(published_version()).search_jobs(query)
    return markdown.render(AIAgent._format_jobs(jobs))


def expertise_form(member_id: str, selected: list[str] | None = None) -> dict:
    key = expertise_key(member_id)
    if selected is None:
        return {"catalog": CATALOG, "max_topics": MAX_TOPICS, "selected": load_topics(key)}
    try:
        choices = validate_topics(selected)
    except ValueError:
        return {**expertise_form(member_id), "error": "Choose up to eight topics from the list."}
    return {"catalog": CATALOG, "max_topics": MAX_TOPICS, "selected": save_topics(key, choices), "saved": True}

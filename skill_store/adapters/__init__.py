"""Adapter plugins for skill source discovery.

Import all adapters here so they register themselves via @register_adapter.
"""

from skill_store.adapters.github_repo import GitHubRepoAdapter, GitHubRepoListAdapter  # noqa: F401
from skill_store.adapters.awesome_list import AwesomeListAdapter  # noqa: F401
from skill_store.adapters.skills_sh import SkillsShAdapter  # noqa: F401
from skill_store.adapters.web_api import WebApiAdapter  # noqa: F401

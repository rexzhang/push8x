from functools import cache

from jinja2.environment import Template
from jinja2.sandbox import SandboxedEnvironment


class MsgTemplate:
    jinja_env = SandboxedEnvironment()

    @cache
    def get_tempalte(self, template: str) -> Template:
        return self.jinja_env.from_string(template)

    def render(self, template_name: str, *args, **kwargs) -> str:
        return self.get_tempalte(template_name).render(*args, **kwargs)

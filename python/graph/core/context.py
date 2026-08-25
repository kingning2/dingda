"""Graph 执行上下文 — LangChain ChatModel + 可选知识。"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from config.settings import AiSettings
from graph.core.config import GraphConfig
from graph.core.model import create_chat_model


class GraphContext:
    """单次 graph invoke 的依赖容器。"""

    def __init__(self, config: GraphConfig) -> None:
        self.config = config
        self._model: BaseChatModel | None = None

    @property
    def model(self) -> BaseChatModel:
        if self._model is None:
            settings = self.config.ai_settings or AiSettings(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                model_name=self.config.model,
            )
            self._model = create_chat_model(settings)
        return self._model

    def llm(self, user: str, *, system: str | None = None) -> str:
        """节点内简单单轮调用 — 走 LangChain model.invoke。"""
        messages = []
        system_text = system if system is not None else self.config.system
        if system_text:
            messages.append(SystemMessage(content=system_text))
        messages.append(HumanMessage(content=user))
        response = self.model.invoke(messages)
        return str(getattr(response, "content", "") or "")

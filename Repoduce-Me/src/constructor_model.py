# from langchain_openai import ChatOpenAI

# import sys
# from pathlib import Path

# # 1) Go from .../Repoduce-Me/test/test_constructor.py -> .../Repoduce-Me
# REPRODUCE_ROOT = Path(__file__).resolve().parents[1]

# # 2) Point to the directory that contains the 'constructor_adapter' package
# ADAPTER_ROOT = REPRODUCE_ROOT / "ConstructorAdapter"
# sys.path.insert(0, str(ADAPTER_ROOT))

# from constructor_adapter import StatelessConstructorAdapter

# class ConstructorModel(ChatOpenAI):
#     constructor_adapter: StatelessConstructorAdapter

#     def __init__(self, **kwargs):
#         if 'constructor_adapter' not in kwargs:
#             adapter_kwargs = {}
#             if 'model' in kwargs:
#                 adapter_kwargs['llm_alias'] = kwargs['model']

#             kwargs['constructor_adapter'] = StatelessConstructorAdapter(**adapter_kwargs)

#         constructor_adapter = kwargs['constructor_adapter']
#         kwargs['api_key'] = 'unused'
#         kwargs['base_url'] = f"{constructor_adapter.api_url}/knowledge-models/{constructor_adapter.km_id}"
#         kwargs['model'] = constructor_adapter.llm_alias

#         ChatOpenAI.__init__(self, **kwargs)

#     def _get_request_payload(self, *args, **kwargs):
#         res = super()._get_request_payload(*args, **kwargs)
#         res['extra_headers'] = self.constructor_adapter._get_headers()
#         res['extra_headers']['X-KM-Extension'] = 'direct_llm'

#         return res


# constructor_model.py

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

from langchain_openai import ChatOpenAI

# Resolve project root: .../Repoduce-Me/src/constructor_model.py -> .../Repoduce-Me
REPRODUCE_ROOT = Path(__file__).resolve().parents[1]

# Directory that contains the "constructor_adapter" package
ADAPTER_ROOT = REPRODUCE_ROOT / "ConstructorAdapter"
sys.path.insert(0, str(ADAPTER_ROOT))

from constructor_adapter import StatefulConstructorAdapter  # type: ignore


class ConstructorModel:
    """
    Thin wrapper around ChatOpenAI that wires it up to the Constructor adapter.

    - No subclassing of ChatOpenAI (avoids Pydantic headaches).
    - Exposes .invoke(...) and .ainvoke(...) like a normal LLM.
    """

    def __init__(self, model: Optional[str] = None, **kwargs: Any) -> None:
        # 1) Build the adapter
        adapter_kwargs: Dict[str, Any] = {}
        if model is not None:
            adapter_kwargs["llm_alias"] = model

        self.constructor_adapter = StatefulConstructorAdapter(**adapter_kwargs)

        base_url = f"{self.constructor_adapter.api_url}/knowledge-models/{self.constructor_adapter.km_id}"
        llm_alias = self.constructor_adapter.llm_alias

        # 2) Prepare headers for Constructor
        headers = self.constructor_adapter._get_headers()
        # This is what your previous _get_request_payload override was doing:
        headers["X-KM-Extension"] = "direct_llm"

        # 3) Make sure caller cannot accidentally override these
        kwargs.pop("base_url", None)
        kwargs.pop("api_key", None)
        kwargs.pop("model", None)
        kwargs.pop("default_headers", None)

        # 4) Instantiate the underlying ChatOpenAI client
        self.client = ChatOpenAI(
            api_key="unused",
            base_url=base_url,
            model=llm_alias,
            default_headers=headers,
            **kwargs,
        )

    def invoke(self, prompt: str, **kwargs: Any):
        """
        Synchronous call: returns a ChatMessage-like object with `.content`.
        """
        return self.client.invoke(prompt, **kwargs)

    async def ainvoke(self, prompt: str, **kwargs: Any):
        """
        Async variant if you ever need it.
        """
        return await self.client.ainvoke(prompt, **kwargs)
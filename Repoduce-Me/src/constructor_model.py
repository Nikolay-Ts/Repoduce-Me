from langchain_openai import ChatOpenAI

import sys
from pathlib import Path

# 1) Go from .../Repoduce-Me/test/test_constructor.py -> .../Repoduce-Me
REPRODUCE_ROOT = Path(__file__).resolve().parents[1]

# 2) Point to the directory that contains the 'constructor_adapter' package
ADAPTER_ROOT = REPRODUCE_ROOT / "ConstructorAdapter"
sys.path.insert(0, str(ADAPTER_ROOT))

from constructor_adapter import StatelessConstructorAdapter

class ConstructorModel(ChatOpenAI):
    constructor_adapter: StatelessConstructorAdapter

    def __init__(self, **kwargs):
        if 'constructor_adapter' not in kwargs:
            adapter_kwargs = {}
            if 'model' in kwargs:
                adapter_kwargs['llm_alias'] = kwargs['model']

            kwargs['constructor_adapter'] = StatelessConstructorAdapter(**adapter_kwargs)

        constructor_adapter = kwargs['constructor_adapter']
        kwargs['api_key'] = 'unused'
        kwargs['base_url'] = f"{constructor_adapter.api_url}/knowledge-models/{constructor_adapter.km_id}"
        kwargs['model'] = constructor_adapter.llm_alias

        ChatOpenAI.__init__(self, **kwargs)

    def _get_request_payload(self, *args, **kwargs):
        res = super()._get_request_payload(*args, **kwargs)
        res['extra_headers'] = self.constructor_adapter._get_headers()
        res['extra_headers']['X-KM-Extension'] = 'direct_llm'

        return res

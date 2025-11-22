# ConstructorAdapter
Adapter to the constructor platform

It requires the following environmental variables to be set. In Linux/MacOS this is the syntax:<br>
export CONSTRUCTOR_KM_ID= <I>the knowledge model id </I><br>
export CONSTRUCTOR_API_KEY= <I>the API Key to connect to the platform </I><br>
export CONSTRUCTOR_API_URL="https://training.constructor.app/api/platform-kmapi/v1/"

Please note that the knowledge model id can be obtained in the page of the knowledge model clicking on the sharing icon.

To connect to the model you need to:<br>
 model = ConstructorModel()<br>
In this way the default LLM is used, GPT-4o Mini, additional parameters can be set, please refer to the init file
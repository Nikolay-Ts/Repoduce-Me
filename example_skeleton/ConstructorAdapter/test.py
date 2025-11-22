from constructor_adapter.constructor_stateful_adapter import StatefulConstructorAdapter
from constructor_adapter.constructor_stateless_adapter import StatelessConstructorAdapter

if __name__ == "__main__":
    adapterStateful = StatefulConstructorAdapter()
    print("Retrieving available LLMs Stateful")
    available_llms = adapterStateful.get_available_llms()
    for llms in available_llms:
        alias = llms["alias"]
        llm_id = llms["id"]
        name = llms["name"]
        print(f"Stateful -- LLM Name: {name} alias: {alias}, LLM ID: {llm_id}")
        model_stateful = StatefulConstructorAdapter(llm_alias=alias)
        print(model_stateful.query("What is the Constructor Model?"))

    adapterStateless = StatelessConstructorAdapter()
    print("Retrieving available LLMs Stateless:")
    available_llms_stateless = adapterStateless.get_available_llms()
    for llms in available_llms_stateless:
        alias = llms["alias"]
        llm_id = llms["id"]
        name = llms["name"]
        print(f"Stateless -- LLM Name: {name} alias: {alias}, LLM ID: {llm_id}")
        model_stateless = StatelessConstructorAdapter(llm_alias=alias)
        print(model_stateless.query("What is the Constructor Model?"))


    #print("Stateful Query on default LLM:")
    #model_stateful = StatefulConstructorAdapter()
    #print(model_stateful.query("What is the Constructor Model?"))
    #model_stateful.reset_model()

    #print("Stateful Query on ChatGPT 4.o:")
    #model_stateful_4o = StatefulConstructorAdapter(llm_name="GPT-4o")
 #   print(model_stateful_4o.query("What is the Constructor Model?"))

    #print("Stateful Query on ChatGPT 4.o with extra document:")
    #model_stateful_4o.add_document("sampleFileToUpload.pdf")
    #print("Checking the presence of the new document in the model stateful:")

    #document_names = model_stateful_4o.get_all_documents_names()

    # Print each document name
    #print("Document Names:")
    #for name in document_names:
         #print(name)

    #print(model_stateful_4o.query("What is the Constructor Model?"))



 #   print("Stateless Query on gpt-4o-2024-08-06:")
 #   model_stateless = StatelessConstructorAdapter(llm_name="GPT-4o")
 #   print(model_stateless.query("What is the Constructor Model?"))
 #   document_names = model_stateless.get_all_documents_names()
 #   model_stateless.add_document("sampleFileToUpload.pdf")

    # Print each document name
#    print("Document Names:")
#    for name in document_names:
#        print(name)

#
#     print("Stateless Query on gpt-4o:")
#     model_stateless = StatelessConstructorAdapter(llm_name="gpt-4o")
#     print(model_stateless.query("What is the Constructor Model?"))
#
#     print("Stateless Query on gpt-4o-2024-08-06 with extra document:")
#     model_stateless = StatelessConstructorAdapter(llm_name="gpt-4o-2024-08-06")
#     model_stateless.add_document("sampleFileToUpload.pdf")
#     print(model_stateless.query("What is the Constructor Model?"))
# #    model_stateless.delete_all_documents()


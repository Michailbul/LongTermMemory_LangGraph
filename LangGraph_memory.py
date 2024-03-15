from dotenv import load_dotenv
import os
from langchain_openai.chat_models import ChatOpenAI
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    MessagesPlaceholder,
)
from langchain_core.runnables import RunnablePassthrough
from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import StructuredTool
from enum import Enum
from typing import Optional
from langgraph.prebuilt import ToolExecutor
from langchain_openai.chat_models import ChatOpenAI
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    MessagesPlaceholder,
)
from langchain_core.utils.function_calling import convert_to_openai_function
from typing import TypedDict, Sequence
from langchain_core.messages import BaseMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import FunctionMessage
import json
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolInvocation

from langgraph.graph import StateGraph, END
from prompts import system_prompt_1 as prompt_1
from prompts import system_prompt_2 as prompt_2

# Load .env file
load_dotenv()

# Set model variables
OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
#OPENAI_ORGANIZATION = os.getenv("OPENAI_ORGANIZATION")

# Initialize LangSmith
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_PROJECT"] = "Demos"



prompt = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(prompt_1),
        MessagesPlaceholder(variable_name="messages"),
        (
            "system",
            "Remember, only respond with TRUE or FALSE. Do not provide any other information.",
        ),
    ]
)


llm = ChatOpenAI(
    model="gpt-3.5-turbo-0125",
    streaming = True,
    temperature=0.0
)

sentinel_runnable = {"messages": RunnablePassthrough()} | prompt | llm



class Category(str, Enum):
    Activities_liking = "Likings"
    Activities_disliking = "Dislikings"
    Career_goals = 'Career_goals'
    Family_attribute = "Family_attribute"
    
class Action(str, Enum):
    Create = "Create"
    Update = "Update"
    Delete = "Delete"
    
class AddKnowledge(BaseModel):
    knowledge: str = Field(
        ...,        description="Condensed bit of knowledge to be saved for future reference in the format: [person(s) this is relevant to] [fact to store] (e.g. User doesn't drin alcohol; user has a girlfriend; etc)",
    ) 
    knowledge_old: Optional[str]  = Field(
        ..., description='Condensed bit of knowledge, that is now to be irrelevant (e.g. User may enjoyed eating apples, but now he became allergic o them, hence the old knowledge, is that in the past he liked apples.)',
    )
    category: Category = Field(
        ..., description="Category that this knowledge belongs to"
    )
    action: Action = Field(
        ...,
        description="Whether this knowledge is adding a new record, updating a record, or deleting a record",
    )
    

def modify_knowledge(
    knowledge: str,
    category: str,
    action: str,
    knowledge_old: str = "",
) -> dict:
    print("Modifying knowledge: ", knowledge, knowledge_old, category, action)
    return "Modified knowledge"


tool_modify_knowledge = StructuredTool.from_function(
    func = modify_knowledge, # the function to run when the tool is called
    name = "Knowledge_Modifier",
    description="Add, update, or delete a bit of knowledge", # Used to tell the model how/when/why to use the tool.
    args_schema=AddKnowledge #The input arguments’ schema.
)


agent_tools = [tool_modify_knowledge]
tool_executor = ToolExecutor(agent_tools)


prompt = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(prompt_2),
        MessagesPlaceholder(variable_name="messages"),
    ]
)

llm = ChatOpenAI(
    model="gpt-3.5-turbo-0125",
    #model="gpt-4-0125-preview",
    streaming=True,
    temperature=0.0,
)

#create the tools to bind the model:

tools = [convert_to_openai_function(t) for t in agent_tools]


knowledge_master_runnable = prompt | llm.bind_functions(tools)


class AgentState(TypedDict):
    #List of previous messages in the conversation
    messages: Sequence[BaseMessage]
    #The Long - Term Memories to remember 
    memories: Sequence[str]
    #Whether The info is relevant
    contains_information: str
    

def call_sentinel(state):
    messages = state["messages"]
    #last_message = messages[-1]
    response = sentinel_runnable.invoke(messages)
    return {"contains_information": "TRUE" in response.content and "yes" or "no"}



def should_continue(state):
    messages = state['messages']
    last_message = messages[-1]
    if "function_call" not in last_message.additional_kwargs: #function_call instead of tool_call
        return "end"
    else:
        return "continue"
    
# Define the function that calls the knowledge master
def call_knowledge_master(state):
    messages = state['messages']
    memories = state['memories']
    response = knowledge_master_runnable.invoke(
        {"messages": messages, "memories": memories}
    )
    return {'messages' : messages + [response]}

def call_tool(state):
    messages = state['messages']
    #we know the last message involves at least one tool
    last_message = messages[-1]
    #loop through all tool calls and append the message to our message log
    
    parsed_tool_input = json.loads(last_message.additional_kwargs["function_call"]["arguments"])
    tool_call = last_message.additional_kwargs['function_call']
    print(tool_call['name'])
    action = ToolInvocation(
            tool=tool_call['name'],
            tool_input=parsed_tool_input#
        )
    response = tool_executor.invoke(action)
    function_message= FunctionMessage(content=str(response), name=action.tool)
    
    messages.append(function_message)
    return {"messages" : messages}
    
    
# Initialize a new graph
graph = StateGraph(AgentState) #

# Define the two "Nodes"" we will cycle between
graph.add_node("sentinel", call_sentinel)
graph.add_node("knowledge_master", call_knowledge_master)
graph.add_node("action", call_tool)

# Define all our Edges

# Set the Starting Edge
graph.set_entry_point("sentinel")

# We now add Conditional Edges
graph.add_conditional_edges('sentinel',
                            lambda x: x['contains_information'],
                            {   'yes' : "knowledge_master",
                                "no" : END, 
                            }
)

graph.add_conditional_edges('knowledge_master',
                            should_continue,
                            {
                                "continue" : "action", 
                                "end" : END
                            }
)

# We now add Normal Edges that should always be called after another
graph.add_edge('action', END )

app = graph.compile()



#TODO messages are not being stored. Add a vectorstore

def process_input(user_input):
    inputs = {"messages": [HumanMessage(content=user_input)]}
    for output in app.with_config({'run_name': "Memory"}).stream(inputs):
        # stream() yields dictionaries with output keyed by node name
        for key, value in output.items():
            print(f"Output from node '{key}':")
            print("---")
            print(value)
        print("\n---\n")
        
        
if __name__ == "__main__":
    #app, model = initialize_app()
    # User input loop
    while True:
        user_input = input("Hello, tell me about yourself!")
        #user_input = "What is the weather in prahue"
        if user_input.lower() == 'exit':
            break
        process_input(user_input)
        
        
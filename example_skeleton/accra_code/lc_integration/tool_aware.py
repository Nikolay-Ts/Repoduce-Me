from typing import TypedDict, Annotated, Literal, List, Optional
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import (
    AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
)
from langchain_core.tools import BaseTool

from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_core.language_models import BaseChatModel
import json


# State schema
class AgentState(TypedDict):
    """State for agent with tool support"""
    model: BaseModel
    messages: Annotated[List[BaseMessage], add_messages]
    tools: List[BaseTool]  # Available tools
    tool_call_id_counter: int  # For generating unique IDs


# Structured output schema
class ToolCallSchema(BaseModel):
    name: str = Field(description="Tool name to call")
    arguments: str = Field(description="Tool arguments as JSON object")


class AgentResponseWithTools(BaseModel):
    reasoning: Optional[str] = Field(default=None, description="Your reasoning")
    tool_calls: List[ToolCallSchema] = Field(
        default_factory=list,
        description="Tools to call. Empty if providing direct answer.",
    )
    direct_answer: Optional[str] = Field(
        default=None,
        description="Direct answer if no tools needed"
    )

def call_model_node(state: AgentState) -> dict:
    """Node: Send messages from the state to the model"""
    messages = state["messages"]
    tools = state.get("tools", [])
    counter = state.get("tool_call_id_counter", 0)

    # Filter out ToolMessages and convert them to regular messages
    # Also remove tool_calls from AIMessages before sending to endpoint
    cleaned_messages = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            # Convert ToolMessage to HumanMessage with tool result
            cleaned_messages.append(
                HumanMessage(
                    content=f"Tool {msg.name} returned: {msg.content}"
                )
            )
        elif isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
            # Create AIMessage without tool_calls for the endpoint
            cleaned_messages.append(
                AIMessage(content=msg.content)
            )
        else:
            cleaned_messages.append(msg)

    # Prepare messages with tool descriptions
    enhanced_messages = list(cleaned_messages)

    if tools:
        tools_prompt = f"""You have access to these tools:

{json.dumps([convert_to_openai_tool(t) for t in tools])}

Respond with JSON matching the schema:
- If using tools: set tool_calls with name and arguments, leave direct_answer empty
- If answering directly: set direct_answer, leave tool_calls empty
- Optionally include reasoning

You MUST respond with valid JSON only."""

        # Add tool prompt to system message or create one
        has_system = any(isinstance(m, SystemMessage) for m in enhanced_messages)
        if has_system:
            for i, msg in enumerate(enhanced_messages):
                if isinstance(msg, SystemMessage):
                    enhanced_messages[i] = SystemMessage(
                        content=f"{msg.content}\n\n{tools_prompt}"
                    )
                    break
        else:
            enhanced_messages.insert(0, SystemMessage(content=tools_prompt))

    # Call model with structured output
    model = state.get("model")  # Assume model is in state or passed via context
    response = model.with_structured_output(AgentResponseWithTools).invoke(enhanced_messages)

    # Convert structured response to AIMessage with tool_calls
    tool_calls = []
    for tc in response.tool_calls:
        call_id = f"call_{counter:04d}"
        counter += 1
        tool_calls.append({
            "name": tc.name,
            "args": json.loads(tc.arguments),
            "id": call_id
        })

    # Build content
    content_parts = []
    if response.reasoning:
        content_parts.append(f"Reasoning: {response.reasoning}")
    if response.direct_answer:
        content_parts.append(response.direct_answer)

    msg_kwargs = {'content': "\n".join(content_parts) if content_parts else ""}
    if tool_calls:
        msg_kwargs['tool_calls'] = tool_calls
    ai_message = AIMessage(**msg_kwargs)

    return {
        "messages": [ai_message],
        "tool_call_id_counter": counter
    }


def call_tool_node(state: AgentState) -> dict:
    """Node: Execute tool calls from the last AI message."""
    messages = state["messages"]
    tools = state.get("tools", [])
    last_message = messages[-1]

    # Create tool registry
    tool_registry = {tool.name: tool for tool in tools}

    # Execute each tool call
    tool_messages = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        call_id = tool_call["id"]

        if tool_name not in tool_registry:
            error_msg = f"Tool '{tool_name}' not found"
            tool_messages.append(
                ToolMessage(
                    content=error_msg,
                    tool_call_id=call_id,
                    name=tool_name
                )
            )
            continue

        tool = tool_registry[tool_name]
        result = tool.invoke(tool_args)
        tool_messages.append(
            ToolMessage(
                content=str(result),
                tool_call_id=call_id,
                name=tool_name
            )
        )

    return {"messages": tool_messages}


def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """Conditional edge: Route based on whether tools were called."""
    last_message = state["messages"][-1]

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "end"


def create_tool_aware_agent(
    model: BaseChatModel,
    tools: List[BaseTool]
) -> StateGraph:
    """Create an agent with tool support using structured output instead of real tool calls in API."""
    # Build graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("call_model", call_model_node)
    workflow.add_node("call_tool", call_tool_node)

    # Set entry point
    workflow.set_entry_point("call_model")

    # Add conditional edge: model -> tools or end
    workflow.add_conditional_edges(
        "call_model",
        should_continue,
        {
            "tools": "call_tool",
            "end": END
        }
    )

    # Tool execution loops back to model
    workflow.add_edge("call_tool", "call_model")

    # Compile with initial state setup
    def setup_state(messages, **kwargs):
        return {
            "messages": messages if isinstance(messages, list) else [HumanMessage(content=str(messages))],
            "tools": tools,
            "model": model,
            "tool_call_id_counter": 0,
            **kwargs
        }

    compiled = workflow.compile()
    compiled.setup_state = setup_state

    return compiled

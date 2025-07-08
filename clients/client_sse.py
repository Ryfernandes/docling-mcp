import asyncio
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()
        self.max_iterations = 20  # Prevent infinite loops
    
    async def connect_to_server(self, server_url: str = "http://localhost:8000/sse"):
        """Connect to an MCP server_script_path

        Args:
            server_url: URL of the SSE server endpoint (default: http://localhost:8000/sse)
        """
        print(f"Connecting to SSE server at: {server_url}")

        sse_transport = await self.exit_stack.enter_async_context(sse_client(server_url))
        self.read, self.write = sse_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.read, self.write))

        await self.session.initialize()

        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def process_query(self, query: str, conversation_summary: Optional[str] = None) -> tuple[str, str]:
        """Process a query using Claude and available tools with agentic behavior"""
        messages = []

        if conversation_summary:
            messages.append({
                "role": "assistant",
                "content": f"Previous conversation context: {conversation_summary}"
            })


        messages.append({
            "role": "user",
            "content": query
        })

        response = await self.session.list_tools()
        available_tools = [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]
        
        execution_log = []
        iteration = 0
        
        while iteration < self.max_iterations:
            iteration += 1
            
            response = self.anthropic.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=messages,
                tools=available_tools,
            )

            has_tool_calls = False

            assistant_message_content = list(response.content)
            tool_results = []
            
            # Process all content in the response
            for content in response.content:
                if content.type == "text":
                    execution_log.append(f"Claude: {content.text}")
                    messages.append({
                        "role": "assistant",
                        "content": content.text
                    })
                    
                elif content.type == "tool_use":
                    has_tool_calls = True
                    tool_name = content.name
                    tool_args = content.input
                    
                    execution_log.append(f"🔧 Calling tool '{tool_name}' with args: {tool_args}")
                    
                    try:
                        result = await self.session.call_tool(tool_name, tool_args)
                        execution_log.append(f"✅ Tool result: {result.content}")
                        
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": content.id,
                            "content": result.content
                        })
                        
                    except Exception as e:
                        execution_log.append(f"❌ Tool error: {str(e)}")

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": content.id,
                            "content": f"Error: {str(e)}",
                            "is_error": True
                        })
            
            # If no tool calls were made, we're done
            if has_tool_calls:
                messages.append({"role": "assistant", "content": assistant_message_content})
                messages.append({"role": "user", "content": tool_results})
            else:
                break
        
        if iteration >= self.max_iterations:
            execution_log.append(f"⚠️ Reached maximum iterations ({self.max_iterations})")

        print("\nSystem: Compressing conversation context...")
        
        summary = self.anthropic.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=200,
            messages=messages + [{
                "role": "user",
                "content": "Please provide a brief summary of the conversation so far. Make sure to prioritize the user's goals, actions taken, and any important data like document keys that will be important for the continuation of work. List the most recent actions first"
            }]
        )

        new_summary = summary.content[0]

        return "\n".join(execution_log), new_summary

    async def process_query_with_streaming(self, query: str) -> str:
        """Alternative version with real-time streaming of tool calls"""
        messages = [
            {
                "role": "user",
                "content": query
            }
        ]

        response = await self.session.list_tools()
        available_tools = [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]
        
        print(f"\n🤖 Processing: {query}")
        iteration = 0
        
        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n--- Iteration {iteration} ---")
            
            response = self.anthropic.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=messages,
                tools=available_tools,
            )

            assistant_message_content = []
            has_tool_calls = False
            
            # Process all content in the response
            for content in response.content:
                assistant_message_content.append(content)
                
                if content.type == "text":
                    print(f"Claude: {content.text}")
                    
                elif content.type == "tool_use":
                    has_tool_calls = True
                    tool_name = content.name
                    tool_args = content.input
                    
                    print(f"🔧 Calling '{tool_name}'...")
                    
                    try:
                        result = await self.session.call_tool(tool_name, tool_args)
                        print(f"✅ Success")
                        
                        # Add tool result to message history
                        messages.append({
                            "role": "assistant", 
                            "content": assistant_message_content
                        })
                        messages.append({
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": content.id,
                                    "content": result.content
                                }
                            ]
                        })
                        
                    except Exception as e:
                        print(f"❌ Error: {str(e)}")
                        messages.append({
                            "role": "assistant",
                            "content": assistant_message_content
                        })
                        messages.append({
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": content.id,
                                    "content": f"Error: {str(e)}",
                                    "is_error": True
                                }
                            ]
                        })
            
            # If no tool calls were made, we're done
            if not has_tool_calls:
                print("🏁 Task complete!")
                break
                
            # Reset for next iteration
            assistant_message_content = []
        
        if iteration >= self.max_iterations:
            print(f"⚠️ Reached maximum iterations ({self.max_iterations})")
        
        return "Task completed!"
    
    async def chat_loop(self):
        """Run an interactive chat loop"""
        context = "None. Start of a new conversation."

        print("\nAgentic MCP Client ready")
        print("Type queries, 'stream' for streaming mode, or 'quit' to exit")

        streaming_mode = False
        
        while True:
            try:
                query = input(f"\nQuery{'(streaming)' if streaming_mode else ''}: ").strip()

                if query.lower() == 'quit':
                    break
                elif query.lower() == 'stream':
                    streaming_mode = not streaming_mode
                    print(f"Streaming mode: {'ON' if streaming_mode else 'OFF'}")
                    continue
                elif query.lower() == 'context':
                    print(f"\nCurrent context: {context}")
                    continue
                elif query.lower() == 'reset':
                    context = "None. Start of a new conversation."
                    print("\nContext reset.")
                    continue

                if streaming_mode:
                    await self.process_query_with_streaming(query)
                else:
                    (response, new_context) = await self.process_query(query, context)
                    context = new_context
                    print("\n" + response)

            except Exception as e:
                print(f"\nError: {str(e)}")
                import traceback
                traceback.print_exc()
    
    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

async def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python client.py <url to MCP server>")
        sys.exit(1)
    
    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
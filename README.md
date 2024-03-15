# LongTerm Memory Agents for the Banking Sector

This project showcases the development of a chatbot capable of creating long-term memory agents, particularly tailored for the banking sector. By integrating LangGraph with the chatbot, it dynamically updates its knowledge base based on user interactions, ensuring accurate and up-to-date responses.

## Features

- **Dynamic Knowledge Update:** Utilizes user input to continually expand and refine the chatbot's knowledge base.
- **LangGraph Integration:** Employs LangGraph to manage and navigate complex conversational paths and memory states.
- **GuardRail Implementation:** Incorporates mechanisms to filter out and avoid responding to malicious or irrelevant queries.

## Setup and Installation

1. **Environment Preparation:**
   Load essential configurations from a `.env` file, ensuring API keys and endpoints are set.

2. **Chat Model Setup:**
   Initialize `ChatOpenAI` with the chosen model, tuning it for real-time streaming and zero temperature for deterministic responses.

3. **Knowledge Management:**
   Define tools and runnables for knowledge addition, modification, and deletion, aligning with specified categories and actions.

4. **LangGraph Construction:**
   Assemble a state graph to navigate between checking new information, managing knowledge, and action execution based on the conversational context.
## Running the Application

Execute the app to interact with the chatbot:

```bash
python LangGraph_memory.py

import json
import os
from datetime import datetime
import uuid
from django.conf import settings
from ..models import GlobalMemory, ChatSession, ChatMessage, Goal
from .vectorstore import get_vector_store, get_rag_context
from datetime import datetime
import traceback

def extract_memory(user_input, llm_response, groq_client, MODEL):
    """Extract personalized learning memory using Groq"""
    memory_prompt = f"""### Role
You're a Learning Memory Scanner analyzing conversations to capture CRITICAL information for personalizing future learning experiences.

### Key Focus Areas
Capture ONLY these 5 learning-specific elements:
1. 🎯 **Learning Goals** - Explicit learning objectives/targets
2. 🚧 **Difficulties/Struggles** - Concepts/problems causing confusion
3. 🧠 **Knowledge Gaps** - Missing prerequisites or misunderstandings
4. 🛠️ **Learning Preferences** - Format/style/pace preferences
5. 📈 **Progress Updates** - Milestones/completed topics

### Output Rules
- Return {"save": false} if NO learning-relevant details found
- For valuable insights, return:
{
  "save": true,
  "memory": "Concise 3rd-person summary (max 15 words) using learning terminology",
  "category": "Goals/Difficulties/Preferences/Progress"  # Pick ONE main category
}

### Examples
User: I always get stuck on gradient descent in neural networks
→ {"save": true, "memory": "Struggles with gradient descent in neural networks", "category": "Difficulties"}

User: Can we use more diagrams next time? I'm a visual learner
→ {"save": true, "memory": "Prefers visual explanations with diagrams", "category": "Preferences"}

User: Just finished module 3 on calculus basics
→ {"save": true, "memory": "Completed calculus fundamentals module", "category": "Progress"}

---

### Current Conversation
User: {user_input}
Assistant: {llm_response}

### Analysis
Scan for LEARNING-SPECIFIC signals. Ignore casual/social content.
Only capture explicit statements about the 5 focus areas.

### Rules:
# return only one memory object and nothing else"""

    try:
        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a memory extraction assistant. Always return valid JSON."},
                {"role": "user", "content": memory_prompt}
            ],
            model=MODEL,
            temperature=0.1,
            max_tokens=200
        )
        
        memory_text = response.choices[0].message.content.strip()
        
        # Try to parse JSON
        try:
            memory_data = json.loads(memory_text)
            return memory_data
        except json.JSONDecodeError:
            # If not valid JSON, try to extract from text
            if "save" in memory_text.lower() and "false" in memory_text.lower():
                return {"save": False}
            else:
                return {"save": True, "memory": memory_text}
    
    except Exception as e:
        print(f"Error extracting memory: {str(e)}")
        return {"save": False}
    

def extract_goals(user_input, llm_response, groq_client, MODEL):
    """Extract goals from conversation using Groq"""
    goal_prompt = f"""### Role
You're a Goal Detection Assistant analyzing conversations to identify EXPLICIT goals, tasks, or objectives mentioned by the user.

### Detection Rules
Look for these goal indicators:
1. 🎯 **Direct Goal Statements** - "I want to...", "My goal is...", "I need to..."
2. 📅 **Task Planning** - "I should...", "I plan to...", "By next week I'll..."
3. 🎓 **Learning Objectives** - "I want to learn...", "I need to master..."
4. 🚀 **Project Goals** - "I'm working on...", "I'm building..."
5. 📈 **Achievement Targets** - "I want to achieve...", "I'm aiming for..."

### Output Rules
- Return {{"save": false}} if NO clear goals are mentioned
- For identified goals, return:
{{
  "save": true,
  "goals": [
    {{
      "title": "Clear, concise goal title (max 50 chars)",
      "description": "Detailed description of what user wants to achieve",
      "deadline": "YYYY-MM-DD or null if not mentioned",
      "status": "Not Started"
    }}
  ]
}}

### Examples
User: I want to learn Python programming in the next 3 months
→ {{"save": true, "goals": [{{"title": "Learn Python Programming", "description": "Master Python programming fundamentals and syntax", "deadline": "2024-06-01", "status": "Not Started"}}]}}

User: I need to finish my machine learning project by Friday
→ {{"save": true, "goals": [{{"title": "Complete ML Project", "description": "Finish machine learning project implementation", "deadline": "2024-03-15", "status": "Not Started"}}]}}

User: How's the weather today?
→ {{"save": false}}

---

### Current Conversation
User: {user_input}
Assistant: {llm_response}

### Analysis
Scan for EXPLICIT goal statements. Ignore casual questions or general discussions.
Extract deadline dates if mentioned (convert relative dates like "next week" to actual dates).
Only capture clear, actionable goals."""

    try:
        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a goal extraction assistant. Always return valid JSON. Today's date is " + datetime.now().strftime("%Y-%m-%d")},
                {"role": "user", "content": goal_prompt}
            ],
            model=MODEL,
            temperature=0.1,
            max_tokens=400
        )
        
        goal_text = response.choices[0].message.content.strip()
        
        # Try to parse JSON
        try:
            goal_data = json.loads(goal_text)
            return goal_data
        except json.JSONDecodeError:
            # If not valid JSON, try to extract from text
            if "save" in goal_text.lower() and "false" in goal_text.lower():
                return {"save": False}
            else:
                return {"save": False}
    
    except Exception as e:
        print(f"Error extracting goals: {str(e)}")
        return {"save": False}



def generate_streaming_assistant_response(
    query, 
    session_id, 
    groq_client, 
    max_tokens=3000,
    temperature=0.7,
    max_chunks=3,
    recent_messages_count=5
):
    print(f"Starting new streaming response for query: {query[:50]}...")
    """
    Generate streaming assistant response with memory, goals, and RAG context integration
    
    Args:
        query (str): User's query/prompt
        session_id (str): Session ID for context retrieval
        groq_client: Groq client instance
        max_tokens (int): Maximum tokens for response
        temperature (float): Temperature for response generation
        max_chunks (int): Maximum RAG chunks to include
        recent_messages_count (int): Number of recent messages to include
        
    Yields:
        dict: Streaming response chunks containing 'chunk', 'done', and optional 'error'
              Final chunk includes 'goals_created' and 'memory_saved' metadata
    """
    try:
        # Track metadata for final response
        goals_created = []
        memory_saved = False
        memory_content = ""

        # Get session
        try:
            session = ChatSession.objects.get(id=session_id)
        except ChatSession.DoesNotExist:
            yield {"chunk": "", "done": True, "error": "Invalid session ID"}
            return
        
        # Load memory context
        memory_context = ""
        try:
            global_memory = GlobalMemory.objects.first()
            if global_memory and global_memory.preferences:
                memory_context = global_memory.preferences.strip()
        except Exception as e:
            print(f"Error loading memory context: {str(e)}")
        
        # Load goals context
        goals_context = ""
        try:
            goals = Goal.objects.filter(session=session).order_by('-created_at')
            if goals.exists():
                goals_list = []
                for goal in goals:
                    goal_text = f"- {goal.title} (Status: {goal.status})"
                    if goal.description:
                        goal_text += f": {goal.description}"
                    if goal.deadline:
                        goal_text += f" [Deadline: {goal.deadline.strftime('%Y-%m-%d')}]"
                    goals_list.append(goal_text)
                goals_context = "\n".join(goals_list)
        except Exception as e:
            print(f"Error loading goals context: {str(e)}")
        
        # Get RAG context from uploaded documents
        rag_context = ""
        try:
            vector_store = get_vector_store()
            # Use session_id as pdf_id to get session-specific documents
            rag_context = get_rag_context(query, vector_store, max_chunks=max_chunks, pdf_id=str(session_id))
        except Exception as e:
            print(f"Error loading RAG context: {str(e)}")
        
        # Prepare messages with enhanced system prompt
        messages = []
        
        # Build enhanced system message
        system_message = settings.SYSTEM_PROMPT
        
        if memory_context:
            system_message += f"\n\n### Previous Learning Context:\n{memory_context}\n\nUse this context to personalize your responses and build upon previous interactions."
        
        if goals_context:
            system_message += f"\n\n### User's Goals:\n{goals_context}\n\nKeep these goals in mind when providing assistance. Help the user work towards achieving these goals and provide relevant progress updates."
        
        if rag_context:
            system_message += f"\n\n### Relevant Document Context:\n{rag_context}\n\nUse this document context to provide accurate, detailed answers. Always cite the source document when referencing information from the uploaded documents."
        
        messages.append({"role": "system", "content": system_message})
        
    # Add recent conversation history (excluding the current query)
        try:
            recent_messages = ChatMessage.objects.filter(session=session).order_by('-created_at')[:recent_messages_count]
            # Reverse to get chronological order
            for message in reversed(recent_messages):
                role = "user" if message.is_user else "assistant"
                messages.append({"role": role, "content": message.message})
        except Exception as e:
            print(f"Error loading recent messages: {str(e)}")
        
        # Add current user query to messages
        messages.append({"role": "user", "content": query})
        
        # Generate streaming response using Groq
        stream = groq_client.chat.completions.create(
            messages=messages,
            model=settings.MODEL,
            temperature=temperature,
            max_completion_tokens=max_tokens,
            stream=True,
            stop=None,
            top_p=1,
        )
        
        full_response = ""
        for chunk in stream:
            chunk_content = chunk.choices[0].delta.content or ""
            if chunk_content:  # Only yield non-empty chunks
                full_response += chunk_content
                yield {"chunk": chunk_content, "done": False}
    
        # Save messages to database
        try:
            ChatMessage.objects.create(session=session, message=query, is_user=True)
            obj = ChatMessage.objects.create(session=session, message=full_response, is_user=False)
        except Exception as e:
            print(f"Error saving messages: {str(e)}")
        
        # Extract and save memory if applicable
        try:
            memory_data = extract_memory(query, full_response, groq_client, settings.MODEL)
            if memory_data.get("save", False):
                memory_text = memory_data.get("memory", "")
                if memory_text:
                    global_memory = GlobalMemory.objects.first()
                    if global_memory:
                        global_memory.preferences += f"\n{memory_text}"
                        global_memory.save()
                        memory_saved = True
                        memory_content = memory_text
        except Exception as e:
            print(f"Error extracting/saving memory: {str(e)}")
        
        # Extract and save goals if applicable
        try:
            goals_data = extract_goals(query, full_response, groq_client, settings.MODEL)
            if goals_data.get("save", False):
                goals_list = goals_data.get("goals", [])
                for goal_data in goals_list:
                    try:
                        deadline = None
                        if goal_data.get("deadline"):
                            deadline = datetime.fromisoformat(goal_data["deadline"])
                        
                        goal = Goal.objects.create(
                            session=session,
                            title=goal_data.get("title", ""),
                            description=goal_data.get("description", ""),
                            deadline=deadline,
                            status=goal_data.get("status", "pending")
                        )
                        
                        # Add to goals_created list
                        goals_created.append({
                            "id": goal.id,
                            "title": goal.title,
                            "description": goal.description,
                            "deadline": goal.deadline.isoformat() if goal.deadline else None,
                            "status": goal.status
                        })
                    except Exception as e:
                        print(f"Error creating goal: {str(e)}")
        except Exception as e:
            print(f"Error extracting/saving goals: {str(e)}")
        
        # Final chunk with metadata
        final_chunk = {
            "chunk": "", 
            "done": True,

            "metadata": {
                "new_message_id": obj.id if obj else None,
                "goals_created": goals_created,
                "memory_saved": memory_saved,
                "memory_content": memory_content if memory_saved else None
            }
        }
        print(f"Streaming response completed for query: {query[:50]}...")
        yield final_chunk
        
    except Exception as e:
        traceback.print_exc()
        yield {"chunk": "", "done": True, "error": f"Error generating response: {str(e)}"}


"""
Usage Examples:

1. Basic RAG Answer (Non-streaming):
```python
from django.conf import settings
from groq import Groq
from .utils.groq_utils import generate_assistant_response

groq_client = Groq(api_key=settings.GROQ_API_KEY)

result = generate_assistant_response(
    query="What is machine learning?",
    session_id=1,
    groq_client=groq_client,
    MODEL=settings.MODEL,
    SYSTEM_PROMPT=settings.SYSTEM_PROMPT
)

if result["success"]:
    print(result["response"])
    print(f"Context used: {result['context_used']}")
else:
    print(f"Error: {result['error']}")
```

2. Streaming RAG Answer:
```python
from django.conf import settings
from groq import Groq
from .utils.groq_utils import generate_streaming_assistant_response

groq_client = Groq(api_key=settings.GROQ_API_KEY)

for chunk_data in generate_streaming_assistant_response(
    query="Explain neural networks",
    session_id=1,
    groq_client=groq_client,
    MODEL=settings.MODEL,
    SYSTEM_PROMPT=settings.SYSTEM_PROMPT
):
    if not chunk_data.get("done", False):
        print(chunk_data["chunk"], end="", flush=True)
    else:
        if "error" in chunk_data:
            print(f"Error: {chunk_data['error']}")
        break
```

3. API Endpoints:
- POST /session/{session_id}/rag/ - Non-streaming RAG response
- POST /session/{session_id}/rag/stream/ - Streaming RAG response (Server-Sent Events)

Request body:
```json
{
    "query": "Your question here"
}
```

Response (non-streaming):
```json
{
    "response": "Assistant response here",
    "context_used": {
        "memory": true,
        "goals": false,
        "rag": true
    }
}
```

Response (streaming):
Server-Sent Events format:
```
data: {"chunk": "Hello", "done": false}
data: {"chunk": " world", "done": false}
data: {"chunk": "", "done": true}
```

Features:
- Automatic memory extraction and storage
- Goal extraction and tracking
- RAG context from uploaded PDFs
- Session-based conversation history
- Error handling and fallback responses
- Both streaming and non-streaming modes
"""

